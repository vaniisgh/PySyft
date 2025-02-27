# future
from __future__ import annotations

# stdlib
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# third party
from nacl.signing import VerifyKey

# relative
from ..... import lib
from .....logger import traceback_and_raise
from ....common.serde.serializable import serializable
from ....common.uid import UID
from ....store.storeable_object import StorableObject
from ...abstract.node import AbstractNode
from ..util import check_send_to_blob_storage
from ..util import upload_result_to_s3
from .common import ImmediateActionWithoutReply
from .greenlets_switch import retrieve_object


@serializable(recursive_serde=True)
class RunClassMethodSMPCAction(ImmediateActionWithoutReply):
    __attr_allowlist__ = [
        "path",
        "_self",
        "args",
        "kwargs",
        "id_at_location",
        "seed_id_locations",
        "address",
        "id",
    ]
    """
    When executing a RunClassMethodSMPCAction, a list of SMPCActionMessages is sent to the
    to the same node (using a rabbitMQ)

    Attributes:
         path: the dotted path to the method to call
         _self: a pointer to the object which the method should be applied to.
         args: args to pass to the function. They should be pointers to objects
            located on the :class:`Node` that will execute the action.
         kwargs: kwargs to pass to the function. They should be pointers to objects
            located on the :class:`Node` that will execute the action.
    """

    def __init__(
        self,
        path: str,
        _self: Any,
        args: List[Any],
        kwargs: Dict[Any, Any],
        id_at_location: UID,
        seed_id_locations: int,
        address: UID,
        msg_id: Optional[UID] = None,
    ):
        self.path = path
        self._self = _self
        self.args = args
        self.kwargs = kwargs
        self.id_at_location = id_at_location
        self.seed_id_locations = seed_id_locations
        # logging needs .path to exist before calling
        # this which is why i've put this super().__init__ down here
        super().__init__(address=address, msg_id=msg_id)

    @staticmethod
    def intersect_keys(
        left: Dict[VerifyKey, Optional[UID]], right: Dict[VerifyKey, Optional[UID]]
    ) -> Dict[VerifyKey, Optional[UID]]:
        # get the intersection of the dict keys, the value is the request_id
        # if the request_id is different for some reason we still want to keep it,
        # so only intersect the keys and then copy those over from the main dict
        # into a new one
        intersection = set(left.keys()).intersection(right.keys())
        # left and right have the same keys
        return {k: left[k] for k in intersection}

    @property
    def pprint(self) -> str:
        return f"RunClassMethodSMPCAction({self.path})"

    def __repr__(self) -> str:
        method_name = self.path.split(".")[-1]
        self_name = self._self.__class__.__name__
        arg_names = ",".join([a.__class__.__name__ for a in self.args])
        kwargs_names = ",".join(
            [f"{k}={v.__class__.__name__}" for k, v in self.kwargs.items()]
        )
        return f"RunClassMethodSMPCAction {self_name}.{method_name}({arg_names}, {kwargs_names})"

    def execute_action(self, node: AbstractNode, verify_key: VerifyKey) -> None:
        # relative
        from ....tensor.smpc import context

        # If if there's another object with the same ID.
        node.store.check_collision(self.id_at_location)

        resolved_self = retrieve_object(node, self._self.id_at_location, self.path)
        result_read_permissions = resolved_self.read_permissions

        resolved_args = list()
        tag_args = []
        for arg in self.args:
            r_arg = retrieve_object(node, arg.id_at_location, self.path)

            # TODO: Think of a way to free the memory
            # del node.store[arg.id_at_location]
            result_read_permissions = self.intersect_keys(
                result_read_permissions, r_arg.read_permissions
            )
            resolved_args.append(r_arg.data)
            tag_args.append(r_arg)

        resolved_kwargs = {}
        tag_kwargs = {}
        for arg_name, arg in self.kwargs.items():
            r_arg = retrieve_object(node, arg.id_at_location, self.path)
            # TODO: Think of a way to free the memory
            # del node.store[arg.id_at_location]
            result_read_permissions = self.intersect_keys(
                result_read_permissions, r_arg.read_permissions
            )
            resolved_kwargs[arg_name] = r_arg.data
            tag_kwargs[arg_name] = r_arg

        (
            upcasted_args,
            upcasted_kwargs,
        ) = lib.python.util.upcast_args_and_kwargs(resolved_args, resolved_kwargs)

        method = node.lib_ast(self.path)
        seed_id_locations = self.seed_id_locations

        # TODO: For the moment we don't run any SMPC operation that provides any kwarg
        context.SMPC_CONTEXT = {
            "seed_id_locations": seed_id_locations,
            "node": node,
            "read_permissions": result_read_permissions,
        }
        print("Path and name", self.path)
        result = method(*upcasted_args, **upcasted_kwargs)

        id_at_location = self.id_at_location
        if lib.python.primitive_factory.isprimitive(value=result):
            # Wrap in a SyPrimitive
            result = lib.python.primitive_factory.PrimitiveFactory.generate_primitive(
                value=result, id=id_at_location
            )
        else:
            # TODO: overload all methods to incorporate this automatically
            if hasattr(result, "id"):
                try:
                    if hasattr(result, "_id"):
                        # set the underlying id
                        result._id = id_at_location
                    else:
                        result.id = id_at_location

                    if result.id != id_at_location:
                        raise AttributeError("IDs don't match")
                except AttributeError as e:
                    err = f"Unable to set id on result {type(result)}. {e}"
                    traceback_and_raise(Exception(err))

        # We do not use blob storage support for SMPC,
        # Since we shifted to TensorPointer as the shares in MPCTensor
        # We use this temporary fix, to not regress PhiTensor performance
        if check_send_to_blob_storage(
            obj=result,
            use_blob_storage=getattr(node.settings, "USE_BLOB_STORAGE", False),
        ):
            result = upload_result_to_s3(
                asset_name=self.id_at_location.no_dash,
                dataset_name="",
                domain_id=node.id,
                data=result,
                settings=node.settings,
            )

        if not isinstance(result, StorableObject):
            result = StorableObject(
                id=id_at_location,
                data=result,
                read_permissions=result_read_permissions,
            )

        node.store[id_at_location] = result


# #### NOTE: DO NOT DELETE THIS CODE######
# This code is part of the retrieable actions logic in SMPC
# We might switch to this,if we make a switch to retriable actions instead of greeen threads.
# @staticmethod
# def execute_smpc_action(
#     node: AbstractNode, msg: "SMPCActionMessage", verify_key: VerifyKey
# ) -> Optional[ShareTensor]:
#     # relative
#     from .smpc_action_functions import _MAP_ACTION_TO_FUNCTION

#     func = _MAP_ACTION_TO_FUNCTION[msg.name_action]
#     store_object_self = node.store.get_object(key=msg.self_id)
#     if store_object_self is None:
#         raise KeyError("Object not already in store")

#     _self = store_object_self.data
#     args = [node.store[arg_id].data for arg_id in msg.args_id]

#     kwargs = {}  # type: ignore
#     for key, kwarg_id in msg.kwargs_id.items():
#         data = node.store[kwarg_id].data
#         if data is None:
#             raise KeyError(f"Key {key} is not available")

#         kwargs[key] = data
#     kwargs = {**kwargs, **msg.kwargs}
#     (
#         upcasted_args,
#         upcasted_kwargs,
#     ) = lib.python.util.upcast_args_and_kwargs(args, kwargs)
#     logger.warning(func)

#     if msg.name_action in {"spdz_multiply", "spdz_mask"}:
#         result = func(_self, *upcasted_args, **upcasted_kwargs, node=node)
#     elif msg.name_action == "local_decomposition":
#         result = func(
#             _self,
#             *upcasted_args,
#             **upcasted_kwargs,
#             node=node,
#             read_permissions=store_object_self.read_permissions,
#         )
#     else:
#         result = func(_self, *upcasted_args, **upcasted_kwargs)

#     return result

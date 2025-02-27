# stdlib
from typing import Optional

# third party
from nacl.signing import VerifyKey

# relative
from ...abstract.node_service_interface import NodeServiceInterface
from ..node_service.generic_payload.syft_message import NewSyftMessage as SyftMessage
from .permissions import BasePermission


class UserCanTriageRequest(BasePermission):
    # TODO: Exceptions could fail silently either depending upon the message
    # # or the permission (not sure which one, need to discuss)

    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        return (
            node.users.can_triage_requests(verify_key=verify_key)
            if verify_key
            else False
        )


class UserCanCreateUsers(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        return (
            node.users.can_create_users(verify_key=verify_key) if verify_key else False
        )


class UserCanEditRoles(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        return node.users.can_edit_roles(verify_key=verify_key) if verify_key else False


class UserCanUploadData(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        return (
            node.users.can_upload_data(verify_key=verify_key) if verify_key else False
        )


class IsNodeDaaEnabled(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        msg_payload = msg.payload  # type: ignore

        if node.setup.first(domain_name=node.name).daa and not msg_payload.daa_pdf:  # type: ignore
            return False

        return True


class NoRestriction(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        return True


class UserIsOwner(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:

        msg_kwargs = msg.kwargs  # type: ignore
        user_id = msg_kwargs.get("user_id")

        if not user_id:
            return False

        _target_user = node.users.first(id_int=user_id)
        request_user = (
            node.users.get_user(verify_key=verify_key) if verify_key else None
        )

        _is_owner = False
        if _target_user and request_user:  # If target and request user exists
            if (
                request_user.role["name"] == node.roles.owner_role["name"]
            ):  # If the user has role `Owner`
                _is_owner = True
            elif request_user and (
                _target_user.id_int == request_user.id_int
            ):  # request user is the target user
                _is_owner = True
        return _is_owner


class UserHasWritePermissionToData(BasePermission):
    def has_permission(
        self,
        msg: SyftMessage,
        node: NodeServiceInterface,
        verify_key: Optional[VerifyKey],
    ) -> bool:
        msg_kwargs = msg.kwargs
        id_at_location = msg_kwargs.get("id_at_location")

        if id_at_location:
            storable_obj = node.store.get(key=id_at_location, proxy_only=True)
            return (
                verify_key in storable_obj.write_permissions
                or verify_key == node.root_verify_key
            )

        return False

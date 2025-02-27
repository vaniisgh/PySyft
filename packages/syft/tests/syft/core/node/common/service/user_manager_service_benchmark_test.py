# stdlib
import timeit
from typing import Tuple

# third party
from faker import Faker
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey
from nacl.signing import VerifyKey
import pytest

# syft absolute
import syft as sy
from syft.core.node.common.node_service.success_resp_message import (
    SuccessResponseMessage,
)
from syft.core.node.common.node_service.user_manager.new_user_messages import (
    CreateUserMessage as NewCreateUserMessage,
)
from syft.core.node.common.node_service.user_manager.new_user_messages import (
    DeleteUserMessage as NewDeleteUserMessage,
)
from syft.core.node.common.node_service.user_manager.new_user_messages import (
    GetUserMessage as NewGetUserMessage,
)
from syft.core.node.common.node_service.user_manager.new_user_messages import (
    GetUsersMessage as NewGetUsersMessage,
)
from syft.core.node.common.node_service.user_manager.new_user_messages import (
    UpdateUserMessage as NewUpdateUserMessage,
)
from syft.core.node.common.node_service.user_manager.user_manager_service import (
    UserManagerService,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    CreateUserMessage,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    DeleteUserMessage,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    GetUserResponse,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    GetUsersMessage,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    GetUsersResponse,
)
from syft.core.node.common.node_service.user_manager.user_messages import (
    UpdateUserMessage,
)
from syft.core.node.common.node_service.user_manager.user_messages import GetUserMessage
from syft.core.node.domain_interface import DomainInterface
from syft.core.node.domain_service import DomainServiceClass


def _create_dummy_user(
    faker: Faker, domain: DomainInterface, is_admin: bool = False
) -> Tuple[dict, VerifyKey]:

    # Create dummy user
    private_key = SigningKey.generate()
    verify_key = private_key.verify_key

    # Check if generated email is already been used for another account previously registered.
    email = faker.free_email()
    while domain.users.contain(email=email):
        email = faker.free_email()

    user = {
        "name": faker.name(),
        "email": email,
        "password": faker.password(),
        "budget": faker.random.random() * 100,
        "role": 4 if is_admin else 1,
        "private_key": private_key.encode(HexEncoder).decode("utf-8"),
    }

    return user, verify_key


def _signup_user(
    domain: DomainInterface, user_dict: dict, verify_key: VerifyKey
) -> tuple:
    # Signup the user
    domain.users.signup(
        **user_dict,
        verify_key=verify_key.encode(encoder=HexEncoder).decode("utf-8"),
    )
    user = domain.users.first(
        **{"verify_key": verify_key.encode(encoder=HexEncoder).decode("utf-8")}
    )
    return user, verify_key


# FIXME: Ionesio,Rasswanth Skipped the tests, as the local domain user creation tests used nosql-lite before
# we could replace it with a local version of nosql.
@pytest.mark.skip
class TestCreateUserMessageBenchmarking:
    def setup_users(self, domain: DomainInterface, faker: Faker) -> None:

        # Register domain setup configuration
        domain.setup.register_once(domain_name=domain.name)

        self.do_users = []

        # Create a Data Owner
        user, verify_key = _create_dummy_user(faker, domain, is_admin=True)
        user, verify_key = _signup_user(domain, user, verify_key)
        self.do_users.append((user, verify_key))

    def test_create_user_message(self, domain: sy.Domain, faker: Faker) -> None:

        # Setup users
        self.setup_users(domain, faker)
        _, do_verify_key = self.do_users[0]

        # Create dummy user data
        user1 = {
            "name": faker.name(),
            "email": f"{faker.random_int()}-{faker.free_email()}",
            "password": faker.password(),
            "website": faker.hostname(),
            "institution": faker.company(),
            "budget": faker.random.random() * 100,
            "role": "Data Scientist",
        }

        user2 = {
            "name": faker.name(),
            "email": f"{faker.random_int()}-{faker.free_email()}",
            "password": faker.password(),
            "website": faker.hostname(),
            "institution": faker.company(),
            "budget": faker.random.random() * 100,
            "role": "Data Scientist",
        }

        # Create user message
        old_user_msg = CreateUserMessage(address=domain.id, reply_to=domain.id, **user1)
        new_user_msg = NewCreateUserMessage(
            address=domain.id, reply_to=domain.id, kwargs=user2
        )

        # Benchmark the serialization and de-serialization time
        start = timeit.default_timer()
        old_msg_ser = sy.serialize(old_user_msg)
        end = timeit.default_timer()
        old_msg_ser_time = end - start

        start = timeit.default_timer()
        old_user_msg_deser = sy.deserialize(old_msg_ser)
        end = timeit.default_timer()
        old_msg_deser_time = end - start

        assert old_user_msg_deser == old_user_msg

        print("\nOld Create User Message")
        print("======================")
        print(f"Serializing took {old_msg_ser_time} secs")
        print(f"Deserializing took {old_msg_deser_time} secs")

        start = timeit.default_timer()
        new_msg_ser = sy.serialize(new_user_msg)
        end = timeit.default_timer()
        new_msg_ser_time = end - start

        start = timeit.default_timer()
        new_user_msg_deser = sy.deserialize(new_msg_ser)
        end = timeit.default_timer()
        new_msg_deser_time = end - start

        assert new_user_msg_deser == new_user_msg

        print("\nNew Create User Message")
        print("======================")
        print(f"Serializing took {new_msg_ser_time} secs")
        print(f"Deserializing took {new_msg_deser_time} secs")

        # Benchmark service execution time
        start = timeit.default_timer()
        ums = UserManagerService()
        reply = ums.process(domain, old_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert type(reply) == SuccessResponseMessage
        print("\nCreate User using Old Service")
        print("======================")
        print(f"User Creation took {time_taken} secs")

        start = timeit.default_timer()
        dsc = DomainServiceClass()
        reply = dsc.process(domain, new_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert reply.kwargs is not None
        assert hasattr(reply.payload, "message") is True
        print("\nCreate User using New Service")
        print("======================")
        print(f"User Creation took {time_taken} secs")


@pytest.mark.skip
class TestGetUserMessageBenchmarking:
    def setup_users(self, domain: DomainInterface, faker: Faker):
        self.do_users = []

        # Create a Data Owner
        user, verify_key = _create_dummy_user(faker, domain, is_admin=True)
        user, verify_key = _signup_user(domain, user, verify_key)
        self.do_users.append((user, verify_key))

    def test_get_user_message(self, domain: sy.Domain, faker: Faker) -> None:

        # Setup users
        self.setup_users(domain, faker)
        do_user, do_verify_key = self.do_users[0]

        # Create get user message
        old_user_msg = GetUserMessage(
            address=domain.id, reply_to=domain.id, **{"user_id": do_user.id}
        )
        new_user_msg = NewGetUserMessage(
            address=domain.id,
            reply_to=domain.id,
            kwargs={"user_id": do_user.id},
        )

        # Benchmark the serialization and de-serialization time
        start = timeit.default_timer()
        old_msg_ser = sy.serialize(old_user_msg)
        end = timeit.default_timer()
        old_msg_ser_time = end - start

        start = timeit.default_timer()
        old_user_msg_deser = sy.deserialize(old_msg_ser)
        end = timeit.default_timer()
        old_msg_deser_time = end - start

        assert old_user_msg_deser == old_user_msg

        print("\nOld Get User Message")
        print("======================")
        print(f"Serializing took {old_msg_ser_time} secs")
        print(f"Deserializing took {old_msg_deser_time} secs")

        start = timeit.default_timer()
        new_msg_ser = sy.serialize(new_user_msg)
        end = timeit.default_timer()
        new_msg_ser_time = end - start

        start = timeit.default_timer()
        new_user_msg_deser = sy.deserialize(new_msg_ser)
        end = timeit.default_timer()
        new_msg_deser_time = end - start

        assert new_user_msg_deser == new_user_msg

        print("\nNew Get User Message")
        print("======================")
        print(f"Serializing took {new_msg_ser_time} secs")
        print(f"Deserializing took {new_msg_deser_time} secs")

        # Benchmark service execution time
        start = timeit.default_timer()
        ums = UserManagerService()
        reply = ums.process(domain, old_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert type(reply) == GetUserResponse
        print("\nGet Users using Old Service")
        print("======================")
        print(f"Fetching all users took {time_taken} secs")

        start = timeit.default_timer()
        dsc = DomainServiceClass()
        reply = dsc.process(domain, new_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert reply.kwargs is not None
        print("\nGet Users using New Service")
        print("======================")
        print(f"Fetching all users took {time_taken} secs")


@pytest.mark.skip
class TestGetUsersMessageBenchmarking:
    def setup_users(self, domain: DomainInterface, faker: Faker):
        self.do_users = []

        # Create a Data Owner
        user, verify_key = _create_dummy_user(faker, domain, is_admin=True)
        user, verify_key = _signup_user(domain, user, verify_key)
        self.do_users.append((user, verify_key))

        self.ds_users = []
        # Create two data scientist users
        for _ in range(2):
            user, verify_key = _create_dummy_user(faker, domain)
            user, verify_key = _signup_user(domain, user, verify_key)
            self.ds_users.append((user, verify_key))

    def test_get_users_message(self, domain: DomainInterface, faker: Faker) -> None:
        # Setup users
        self.setup_users(domain, faker)
        _, do_verify_key = self.do_users[0]

        # Create get user message
        old_user_msg = GetUsersMessage(address=domain.id, reply_to=domain.id)
        new_user_msg = NewGetUsersMessage(address=domain.id, reply_to=domain.id)

        # Benchmark the serialization and de-serialization time
        start = timeit.default_timer()
        old_msg_ser = sy.serialize(old_user_msg)
        end = timeit.default_timer()
        old_msg_ser_time = end - start

        start = timeit.default_timer()
        old_user_msg_deser = sy.deserialize(old_msg_ser)
        end = timeit.default_timer()
        old_msg_deser_time = end - start

        assert old_user_msg_deser == old_user_msg

        print("\nOld Get Users Message")
        print("======================")
        print(f"Serializing took {old_msg_ser_time} secs")
        print(f"Deserializing took {old_msg_deser_time} secs")

        start = timeit.default_timer()
        new_msg_ser = sy.serialize(new_user_msg)
        end = timeit.default_timer()
        new_msg_ser_time = end - start

        start = timeit.default_timer()
        new_user_msg_deser = sy.deserialize(new_msg_ser)
        end = timeit.default_timer()
        new_msg_deser_time = end - start

        assert new_user_msg_deser == new_user_msg

        print("\nNew Get Users Message")
        print("======================")
        print(f"Serializing took {new_msg_ser_time} secs")
        print(f"Deserializing took {new_msg_deser_time} secs")

        # Benchmark service execution time
        start = timeit.default_timer()
        ums = UserManagerService()
        reply = ums.process(domain, old_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert type(reply) == GetUsersResponse
        print("\nGet Users using Old Service")
        print("======================")
        print(f"Fetching all users took {time_taken} secs")

        start = timeit.default_timer()
        dsc = DomainServiceClass()
        reply = dsc.process(domain, new_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert reply.payload is not None
        assert hasattr(reply.payload, "users") is True
        print("\nGet Users using New Service")
        print("======================")
        print(f"Fetching all users took {time_taken} secs")


@pytest.mark.skip
class TestUpdateUserMessageBenchmarking:
    def setup_users(self, domain: DomainInterface, faker: Faker):
        self.do_users = []

        # Create a Data Owner
        user, verify_key = _create_dummy_user(faker, domain, is_admin=True)
        user, verify_key = _signup_user(domain, user, verify_key)
        self.do_users.append((user, verify_key))

        self.ds_users = []
        # Create two data scientist users
        for _ in range(2):
            user, verify_key = _create_dummy_user(faker, domain)
            user, verify_key = _signup_user(domain, user, verify_key)
            self.ds_users.append((user, verify_key))

    def test_update_user_message(self, domain: DomainInterface, faker: Faker) -> None:

        self.setup_users(domain, faker)

        _, do_verify_key = self.do_users[0]
        ds_user_1, _ = self.ds_users[0]
        ds_user_2, _ = self.ds_users[1]

        user1_updated_info = {
            "user_id": ds_user_1.id,
            "name": faker.name(),
            "email": faker.free_email(),
            "institution": faker.company(),
            "website": faker.hostname(),
            "budget": faker.random.random() * 100,
        }

        print(user1_updated_info)

        user2_updated_info = {
            "user_id": ds_user_2.id,
            "name": faker.name(),
            "email": faker.free_email(),
            "institution": faker.company(),
            "website": faker.hostname(),
            "budget": faker.random.random() * 100,
        }

        print(user2_updated_info)

        # Create user update messages
        old_user_msg = UpdateUserMessage(
            address=domain.id, reply_to=domain.id, **user1_updated_info
        )
        new_user_msg = NewUpdateUserMessage(
            address=domain.id, reply_to=domain.id, kwargs=user2_updated_info
        )

        # Benchmark the serialization and de-serialization time
        start = timeit.default_timer()
        old_msg_ser = sy.serialize(old_user_msg)
        end = timeit.default_timer()
        old_msg_ser_time = end - start

        start = timeit.default_timer()
        old_user_msg_deser = sy.deserialize(old_msg_ser)
        end = timeit.default_timer()
        old_msg_deser_time = end - start

        assert old_user_msg_deser == old_user_msg

        print("\nOld Update User Message")
        print("======================")
        print(f"Serializing took {old_msg_ser_time} secs")
        print(f"Deserializing took {old_msg_deser_time} secs")

        start = timeit.default_timer()
        new_msg_ser = sy.serialize(new_user_msg)
        end = timeit.default_timer()
        new_msg_ser_time = end - start

        start = timeit.default_timer()
        new_user_msg_deser = sy.deserialize(new_msg_ser)
        end = timeit.default_timer()
        new_msg_deser_time = end - start

        assert new_user_msg_deser == new_user_msg

        print("\nNew Update User Message")
        print("======================")
        print(f"Serializing took {new_msg_ser_time} secs")
        print(f"Deserializing took {new_msg_deser_time} secs")

        # Benchmark service execution time
        start = timeit.default_timer()
        ums = UserManagerService()
        reply = ums.process(domain, old_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        assert type(reply) == SuccessResponseMessage
        print("\nUpdate User using Old Service")
        print("======================")
        print(f"Updating information took {time_taken} secs")

        start = timeit.default_timer()
        dsc = DomainServiceClass()
        reply = dsc.process(domain, new_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        time_taken = end - start

        # assert reply.kwargs is not None
        print("\nUpdate User using New Service")
        print("======================")
        print(f"Updating information took {time_taken} secs")


@pytest.mark.skip
class TestDeleteUserMessageBenchmarking:
    def setup_users(self, domain: DomainInterface, faker: Faker):
        self.do_users = []

        # Create a Data Owner
        user, verify_key = _create_dummy_user(faker, domain, is_admin=True)
        user, verify_key = _signup_user(domain, user, verify_key)
        self.do_users.append((user, verify_key))

        self.ds_users = []
        # Create two data scientist users
        for _ in range(2):
            user, verify_key = _create_dummy_user(faker, domain)
            user, verify_key = _signup_user(domain, user, verify_key)
            self.ds_users.append((user, verify_key))

    def test_delete_user_message(self, domain: DomainInterface, faker: Faker) -> None:
        # Setup users
        self.setup_users(domain, faker)
        _, do_verify_key = self.do_users[0]
        ds_user1, _ = self.ds_users[0]
        ds_user2, _ = self.ds_users[1]

        # Create Old and New User Delete Messages
        old_user_msg = DeleteUserMessage(
            address=domain.id, reply_to=domain.id, **{"user_id": ds_user1.id}
        )
        new_user_msg = NewDeleteUserMessage(
            address=domain.id,
            reply_to=domain.id,
            kwargs={"user_id": ds_user2.id},
        )

        # Benchmark serialization and de-serialization time
        start = timeit.default_timer()
        old_msg_ser = sy.serialize(old_user_msg)
        end = timeit.default_timer()
        old_msg_ser_time = end - start

        start = timeit.default_timer()
        old_user_msg_deser = sy.deserialize(old_msg_ser)
        end = timeit.default_timer()
        old_msg_deser_time = end - start

        assert old_user_msg_deser == old_user_msg

        print("\nOld Delete User Message")
        print("======================")
        print(f"Serializing took {old_msg_ser_time} secs")
        print(f"Deserializing took {old_msg_deser_time} secs")

        start = timeit.default_timer()
        new_msg_ser = sy.serialize(new_user_msg)
        end = timeit.default_timer()
        new_msg_ser_time = end - start

        start = timeit.default_timer()
        new_user_msg_deser = sy.deserialize(new_msg_ser)
        end = timeit.default_timer()
        new_msg_deser_time = end - start

        assert new_user_msg_deser == new_user_msg

        print("\nNew Delete User Message")
        print("======================")
        print(f"Serializing took {new_msg_ser_time} secs")
        print(f"Deserializing took {new_msg_deser_time} secs")

        # Benchmark service execution time
        start = timeit.default_timer()
        ums = UserManagerService()
        reply = ums.process(domain, old_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        del_using_old_service = end - start

        assert type(reply) == SuccessResponseMessage
        print("\nDelete User using Old Service")
        print("======================")
        print(f"Deletion took {del_using_old_service} secs")

        start = timeit.default_timer()
        dsc = DomainServiceClass()
        reply = dsc.process(domain, new_user_msg, verify_key=do_verify_key)
        end = timeit.default_timer()
        del_using_new_service = end - start

        # assert reply.kwargs is not None
        print("\nDelete User using New Service")
        print("======================")
        print(f"Deletion took {del_using_new_service} secs")

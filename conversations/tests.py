"""Conversation model tests."""
import pytest
from leads.models import CustomerIdentity, Customer
from conversations.models import Conversation, Message


@pytest.mark.django_db
def test_conversation_with_messages():
    identity = CustomerIdentity.objects.create(external_id="test_001")
    customer = Customer.objects.create(identity=identity)
    conv = Conversation.objects.create(customer=customer)
    Message.objects.create(conversation=conv, role="user", content="مرحبا")
    Message.objects.create(conversation=conv, role="assistant", content="أهلاً بك!")
    assert conv.messages.count() == 2

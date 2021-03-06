from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, decorators, status
from rest_framework.response import Response
from django.utils.translation import ugettext_lazy as _

from .models import Message
from .serializers import ComposeSerializer, ReadMessageSerializer


class MessageViewSet(viewsets.GenericViewSet):
    queryset = Message.objects.all()
    serializer_class = ComposeSerializer

    @decorators.action(methods=['get'], detail=False)
    def inbox(self, request):
        """
        Displays a list of received messages for the current user.
        """
        message_list = Message.objects.inbox_for(request.user)
        serialized_messages = self.serialized_messages(message_list)

        return Response({
            'messages_list': serialized_messages,
        }, status=status.HTTP_200_OK)

    @decorators.action(methods=['get'], detail=False)
    def outbox(self, request):
        """
        Displays a list of sent messages by the current user.
        """
        message_list = Message.objects.outbox_for(request.user)
        serialized_messages = self.serialized_messages(message_list)

        return Response({
            'messages_list': serialized_messages,
        }, status=status.HTTP_200_OK)

    @decorators.action(methods=['get'], detail=False)
    def trash(self, request):
        """
        Displays a list of deleted messages.
        Hint: A Cron-Job could periodically clean up old messages, which are deleted
        by sender and recipient.
        """
        message_list = Message.objects.trash_for(request.user)
        serialized_messages = self.serialized_messages(message_list)
        return Response({
            'messages_list': serialized_messages,
        })

    @decorators.action(methods=['post'], detail=False)
    def compose(self, request):
        """
        Processes and saves the ``composed`` message.
        Required Arguments:
            ``recipient``: users of a django auth model or provided by the users,
                           who should receive the message, optionally multiple users
                           can be passed in a list
        """
        serializer = ComposeSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            message_instances = serializer.save(sender=request.user)
            return Response({
                'messages_list': message_instances
            }, status=status.HTTP_201_CREATED)

    @decorators.action(methods=['post'], detail=True)
    def reply(self, request, pk):
        """
        processes a reply message to a given message (specified via ``message_id``).
        """
        parent = get_object_or_404(Message, pk=pk)
        if parent.sender != request.user and parent.recipient != request.user:
            raise Http404

        serializer = ComposeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_instances = serializer.save(sender=request.user, parent_msg=parent)
        return Response({
            'message': message_instances
        }, status=status.HTTP_201_CREATED)

    @decorators.action(methods=['put'], detail=True)
    def delete(self, request, pk):
        """
        Marks a message as deleted by sender or recipient. The message is not
        really removed from the database, because two users must delete a message
        before it's save to remove it completely.
        A cron-job should prune the database and remove old messages which are
        deleted by both users.
        As a side effect, this makes it easy to implement a trash with undelete.
        """
        now = timezone.now()
        message = get_object_or_404(Message, pk=pk)

        deleted = False
        if message.sender == request.user:
            message.sender_deleted_at = now
            deleted = True
        if message.recipient == request.user:
            message.recipient_deleted_at = now
            deleted = True
        if deleted:
            message.save()
            return Response({
                _("Message successfully deleted.")
            }, status=status.HTTP_204_NO_CONTENT)
        raise Http404

    @decorators.action(methods=['put'], detail=True)
    def undelete(self, request, pk):
        """
        Recovers a message from trash. This is achieved by removing the
        ``(sender|recipient)_deleted_at`` from the model.
        """
        message = get_object_or_404(Message, pk=pk)
        undeleted = False

        if message.sender == request.user:
            message.sender_deleted_at = None
            undeleted = True
        if message.recipient == request.user:
            message.recipient_deleted_at = None
            undeleted = True
        if undeleted:
            message.save()
            return Response({_("Message successfully recovered.")}, status=status.HTTP_200_OK)
        raise Http404

    @decorators.action(methods=['get'], detail=True)
    def view(self, request, pk):
        """
        Shows a single message.``message_id`` argument is required.
        The user is only allowed to see the message, if he is either
        the sender or the recipient. If the user is not allowed a 404
        is raised.
        If the user is the recipient and the message is unread
        ``read_at`` is set to the current datetime.
        """
        now = timezone.now()
        message = get_object_or_404(Message, pk=pk)

        if (message.sender != request.user) and (message.recipient != request.user):
            raise Http404
        if message.recipient == request.user and message.recipient_deleted_at is not None:
            raise Http404
        if message.sender == request.user and message.sender_deleted_at is not None:
            raise Http404

        if message.read_at is None and message.recipient == request.user:
            message.read_at = now
            message.save()

        return Response({
            'message': ReadMessageSerializer(message).data
        })

    @staticmethod
    def serialized_messages(messages_list):
        serialized_messages_list = []
        for msg in messages_list:
            ser_message = ReadMessageSerializer(msg)
            serialized_messages_list.append(ser_message.data)
        return serialized_messages_list

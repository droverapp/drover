from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_group, name='create_group'),
    path('<group_id>', views.view_group, name='view_group'),
    path('<group_id>/edit/', views.edit_group, name='edit_group'),
    path('<group_id>/add-member/', views.add_group_member, name='add_group_member'),
    path('<group_id>/edit-member/<member_id>', views.edit_group_member, name='edit_group_member'),
    path('<group_id>/remove-member/<member_id>', views.remove_group_member, name='remove_group_member'),
    path('<group_id>/send-message/', views.send_message, name='send_message'),
    path('<group_id>/invite/', views.invite, name='invite'),
    path('<group_id>/inbox/', views.inbox, name='inbox'),
    path('<group_id>/message/<message_id>', views.message_details, name='message_details'),
    path('<group_id>/conversation/', views.conversations, name='conversations'),
    path('<group_id>/conversation/<message_id>', views.conversation_details, name='conversation_details'),
]

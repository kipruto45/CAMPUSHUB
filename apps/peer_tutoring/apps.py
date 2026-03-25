"""
App configuration for Peer Tutoring
"""

from django.apps import AppConfig


class PeerTutoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.peer_tutoring'
    verbose_name = 'Peer Tutoring'

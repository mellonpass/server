from django.http import HttpRequest
from ipware import get_client_ip


# Used for ratelimiting.
# Detect CLIENT_IP properly using ipware.
def rl_client_ip(group, request: HttpRequest):
    client_ip, _ = get_client_ip(request)
    return client_ip

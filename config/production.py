from config.base import *

DEBUG = False
CORS_ALLOW_ALL_ORIGINS = False

# JWTAuthToken
JWT_AUTH_ENABLE = True
JWT_AUTH_PROTECTD_VIEWS = ["mp_graphql.views.mp_graphql_view"]

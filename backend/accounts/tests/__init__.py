"""
Init file for accounts tests.
"""
# View tests
from .views.test_email_views import *
from .views.test_logout_views import *
from .views.test_password_views import *
from .views.test_phone_number_views import *
from .views.test_profile_views import *
from .views.test_sign_in_views import *
from .views.test_sign_up_views import *

# Service tests
from .services.test_services import *

# Other tests
from .test_authentication import *
from .test_commands import *
from .test_middleware import *
from .test_models import *
from .test_utils import *


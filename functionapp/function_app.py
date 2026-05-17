
from pathlib import Path
import sys
import os
import azure.functions as func


# Resolve the 'api' package in both local dev and Azure zip deploy.
# Local dev: function_app.py is in functionapp/, api/ is a sibling dir  -> parents[1]/api
# Azure zip: function_app.py is at wwwroot root, api/ is beside it      -> parent/api
_this = Path(__file__).resolve()
for _candidate in (_this.parent / "api", _this.parents[1] / "api"):
    if (_candidate / "app").is_dir():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        # Set CWD to the api package so relative data paths (data/index/) resolve correctly
        os.chdir(_candidate)
        break


def get_fastapi_app():
    from app.main import app as fastapi_app
    return fastapi_app

app = func.AsgiFunctionApp(app=get_fastapi_app(), http_auth_level=func.AuthLevel.ANONYMOUS)

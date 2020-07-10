import os, pathlib

import fastapi as fast
import environs
import aiofiles
import starlette as star


from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask
from flask_autoindex import AutoIndex
import fastapi_users as fastusrs

from tortoise.contrib.starlette import register_tortoise




ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = '/'.join((ROOT_DIR, 'results'))
DATABASE_URL = f"sqlite://{ROOT_DIR}/test.db"
print(RESULTS_DIR)
env = environs.Env()
env.read_env(recurse=False)
SECRET = "SECRET"
HOST = env('DATA_SERVER_PUBLIC_HOST') or 'localhost'
PORT = env('DATA_SERVER_PORT') or '8000'
VALID_EXTENSIONS = (
    '.png', '.jpeg', '.jpg',
    '.tar.gz', '.tar.xz', '.tar.bz2'
)


class User(fastusrs.models.BaseUser):
    pass


class UserCreate(fastusrs.models.BaseUserCreate):
    pass


class UserUpdate(User, fastusrs.models.BaseUserUpdate):
    pass


class UserDB(User, fastusrs.models.BaseUserDB):
    pass


class UserModel(fastusrs.db.TortoiseBaseUserModel):
    pass

app = fast.FastAPI()


# Flask AutoIndex module for exploring directories
flask_app = Flask(__name__)
AutoIndex(flask_app, browse_root = RESULTS_DIR)
app.mount('/results', WSGIMiddleware(flask_app))


user_db = fastusrs.db.TortoiseUserDatabase(UserDB, UserModel)

register_tortoise(
    app,
    # db_url = DATABASE_URL,
    db_url = "sqlite://:memory:",
    modules = {"models": ["app.main"]},
    generate_schemas = True)



jwt_authentication = fastusrs.authentication.JWTAuthentication(
    secret=SECRET, 
    lifetime_seconds=3600,
    tokenUrl='/auth/jwt/login')
cookie_authentication = fastusrs.authentication.CookieAuthentication(
    secret=SECRET, 
    lifetime_seconds=3600)
auth_backends = [
    jwt_authentication,
    cookie_authentication
]


def on_after_register(user: UserDB, request: fast.Request):
    print(f"User {user.id} has registered.")


app_users = fastusrs.FastAPIUsers(
    user_db,
    auth_backends,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)
app.include_router(
    app_users.get_auth_router(jwt_authentication),
    prefix = '/auth/jwt',
    tags = ['auth']
)
app.include_router(
    app_users.get_register_router(on_after_register),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    app_users.get_users_router(), 
    prefix = '/users', 
    tags=['users']
)


@app.get('/')
async def root(): 
    return star.responses.RedirectResponse(url = '/results')


@app.get('/results/{filename}')
async def results(filename):
    if not pathlib.Path('/'.join((ROOT_DIR, 'results', filename))).exists():
        raise fast.HTTPException(
            status_code = 404,
            detail = f"{filename} was not found in results."
        )
    return fast.responses.FileResponse(
        path = '/'.join((
            'results',
            filename
        ))
    )   


@app.post('/api')
async def upload(
    request: fast.Request, 
    file: fast.UploadFile = fast.File(...)):

    print(request.client.host)

    if not file.filename.endswith(VALID_EXTENSIONS):
        raise fast.HTTPException(
            status_code = 400,
            detail = 'File extension not allowed.')

    dest = pathlib.Path('/'.join((
        RESULTS_DIR,
        file.filename
    )))
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(dest)

    async with aiofiles.open(dest, 'wb') as buffer:
        await file.seek(0)
        contents = await file.read()
        await buffer.write(contents)

    return f'{HOST}:{PORT}/results/{file.filename}'



import os, pathlib

import fastapi as fast
import environs
import aiofiles
import starlette as star
import databases

from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask
from flask_autoindex import AutoIndex
from fastapi_users import models
from fastapi_users import FastAPIUsers

import motor.motor_asyncio
from fastapi_users.authentication import (JWTAuthentication, CookieAuthentication)
from fastapi_users.db import MongoDBUserDatabase


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = '/'.join((ROOT_DIR, 'results'))

DATABASE_URL = 'mongodb://localhost:27107'
print(RESULTS_DIR)
env = environs.Env()
env.read_env(recurse=False)
SECRET = "SECRET"
HOST = env('DATA_SERVER_PUBLIC_HOST')
PORT = env('DATA_SERVER_PORT') 
VALID_EXTENSIONS = (
    '.png', '.jpeg', '.jpg',
    '.tar.gz', '.tar.xz', '.tar.bz2'
)


class User(models.BaseUser):
    pass


class UserCreate(models.BaseUserCreate):
    pass


class UserUpdate(User, models.BaseUserUpdate):
    pass


class UserDB(User, models.BaseUserDB):
    pass


app = fast.FastAPI()


# Flask AutoIndex module for exploring directories
flask_app = Flask(__name__)
AutoIndex(flask_app, browse_root = RESULTS_DIR)
app.mount('/results', WSGIMiddleware(flask_app))


client = motor.motor_asyncio.AsyncIOMotorClient(
    DATABASE_URL
)
db = client['database_name']
collection = db['users']
user_db = MongoDBUserDatabase(UserDB, collection)



jwt_authentication = JWTAuthentication(secret=SECRET, lifetime_seconds=3600,
    tokenUrl='/auth/jwt/login')
cookie_authentication = CookieAuthentication(secret=SECRET, lifetime_seconds=3600)
auth_backends = [
    jwt_authentication,
    cookie_authentication
]


def on_after_register(user: UserDB, request: fast.Request):
    print(f"User {user.id} has registered.")


api_users = FastAPIUsers(
    user_db,
    auth_backends,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)
app.include_router(
    api_users.get_auth_router(jwt_authentication),
    prefix = '/auth/jwt',
    tags = ['auth']
)
app.include_router(
    api_users.get_register_router(on_after_register),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    api_users.get_users_router(), 
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

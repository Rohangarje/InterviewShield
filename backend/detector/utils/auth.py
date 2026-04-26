import bcrypt
import json
from datetime import datetime
from .mongo_client import get_collection

USERS_COLLECTION = 'users'

def hash_password(password):
    """Securely hash password w/ bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify plain vs hashed password"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def user_exists(username):
    """Check if user exists"""
    coll = get_collection()
    if coll is not None:
        return coll.find_one({'username': username}, {'_id': 1})
    return None

def create_user(username, email, password, resume_url=None):
    """Create new user in Mongo"""
    coll = get_collection()
    if coll is not None and not user_exists(username):
        hashed_pw = hash_password(password)
        user_doc = {
            'username': username,
            'email': email,
            'password': hashed_pw,
            'resume_url': resume_url,
            'created_at': datetime.utcnow().isoformat()
        }
        result = coll.insert_one(user_doc)
        return result.inserted_id
    return None

def update_user_resume(username, resume_url):
    """Update user's resume URL"""
    coll = get_collection()
    if coll is not None:
        result = coll.update_one(
            {'username': username},
            {'$set': {'resume_url': resume_url, 'updated_at': datetime.utcnow().isoformat()}}
        )
        return result.modified_count > 0
    return False

def get_user_resume(username):
    """Get user's resume URL"""
    coll = get_collection()
    if coll is not None:
        user = coll.find_one({'username': username}, {'resume_url': 1})
        if user:
            return user.get('resume_url')
    return None

def authenticate_user(username, password):
    """Verify login, return user doc if valid"""
    coll = get_collection()
    if coll is not None:
        user = coll.find_one({'username': username})
        if user is not None and verify_password(password, user['password']):
            return user
    return None

""" Initialize environment variables from a .env file located in the root directory. """
import os

from dotenv import dotenv_values

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

dotenv_path = os.path.join(ROOT_DIR, '.env')

envs = dotenv_values(dotenv_path, verbose=True)
# globals().update(_env_vars)

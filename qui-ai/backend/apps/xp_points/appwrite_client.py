from appwrite.client import Client
from appwrite.services.databases import Databases
import os

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT")) \
      .set_project(os.getenv("APPWRITE_PROJECT_ID")) \
      .set_key(os.getenv("APPWRITE_API_KEY"))

databases = Databases(client)
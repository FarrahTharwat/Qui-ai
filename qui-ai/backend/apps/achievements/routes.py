from fastapi import APIRouter, HTTPException
from achievements.models import AchievementRequest
from achievements.appwrite_client import databases
from appwrite.query import Query
from appwrite.exception import AppwriteException
import os, uuid
from datetime import datetime

# # router = APIRouter()

# # @router.post("/check")
# # def check_achievements(request: AchievementRequest):
# #     try:
# #         xp_docs = databases.list_documents(
# #             database_id=os.getenv("APPWRITE_DB"),
# #             collection_id=os.getenv("XP_COLLECTION"),
# #             queries=[
# #                 Query.equal("user_id", [request.user_id])  # ✅ fix: wrap in list
# #             ]
# #         )

# #         total_xp = sum(doc.get("xp", 0) for doc in xp_docs["documents"])
# #         unlocked = []

# #         if total_xp >= 50:
# #             unlocked.append("XP Master")

# #         for title in unlocked:
# #             exists = databases.list_documents(
# #                 database_id=os.getenv("APPWRITE_DB"),
# #                 collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                 queries=[
# #                     Query.equal("user_id", [request.user_id]),  # ✅ fix
# #                     Query.equal("achievement", [title])         # ✅ fix
# #                 ]
# #             )
# #             if not exists["documents"]:
# #                 databases.create_document(
# #                     database_id=os.getenv("APPWRITE_DB"),
# #                     collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                     document_id=str(uuid.uuid4()),
# #                     data={
# #                         "user_id": request.user_id,
# #                         "achievement": title,
# #                         "timestamp": datetime.utcnow().isoformat()
# #                     }
# #                 )

# #         return {"unlocked": unlocked}

# #     except AppwriteException as e:
# #         raise HTTPException(status_code=500, detail=f"Appwrite error: {str(e)}")

# # from fastapi import APIRouter, HTTPException
# # from achievements.models import AchievementRequest
# # from achievements.appwrite_client import databases
# # from appwrite.query import Query
# # from appwrite.exception import AppwriteException
# # import os, uuid
# # from datetime import datetime

# # router = APIRouter()

# # @router.post("/check")
# # def check_achievements(request: AchievementRequest):
# #     try:
# #         # ✅ Ensure user_id is wrapped in a list
# #         xp_docs = databases.list_documents(
# #             database_id=os.getenv("APPWRITE_DB"),
# #             collection_id=os.getenv("XP_COLLECTION"),
# #             queries=[Query.equal("user_id", [request.user_id])]
# #         )

# #         # ✅ Safely extract XP from each document
# #         total_xp = sum(doc.get("xp", 0) for doc in xp_docs["documents"])
# #         unlocked = []

# #         # ✅ Example logic: Unlock "XP Master" if XP ≥ 50
# #         if total_xp >= 50:
# #             unlocked.append("XP Master")

# #         for achievement in unlocked:
# #             # ✅ Check if achievement already exists
# #             existing = databases.list_documents(
# #                 database_id=os.getenv("APPWRITE_DB"),
# #                 collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                 queries=[
# #                     Query.equal("user_id", [request.user_id]),
# #                     Query.equal("achievement", [achievement])
# #                 ]
# #             )

# #             if not existing["documents"]:
# #                 # ✅ Insert new achievement with timestamp
# #                 databases.create_document(
# #                     database_id=os.getenv("APPWRITE_DB"),
# #                     collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                     document_id=str(uuid.uuid4()),
# #                     data={
# #                         "user_id": request.user_id,
# #                         "achievement": achievement,
# #                         "timestamp": datetime.utcnow().isoformat()
# #                     }
# #                 )

# #         return {"unlocked": unlocked}

# #     except AppwriteException as e:
# #         raise HTTPException(status_code=500, detail=f"Appwrite error: {str(e)}")

# # from fastapi import APIRouter, HTTPException
# # from pydantic import BaseModel
# # from achievements.appwrite_client import databases
# # from appwrite.query import Query
# # from appwrite.exception import AppwriteException
# # import os
# # import uuid
# # from datetime import datetime

# # router = APIRouter()

# # class AchievementRequest(BaseModel):
# #     user_id: str

# # @router.post("/check")
# # async def check_achievements(request: AchievementRequest):
# #     try:
# #         # Load and validate environment variables
# #         db_id = os.getenv("APPWRITE_DB")
# #         xp_collection = os.getenv("XP_COLLECTION")
# #         achievements_collection = os.getenv("ACHIEVEMENTS_COLLECTION")

# #         if not all([db_id, xp_collection, achievements_collection]):
# #             print("❌ Missing environment variables: APPWRITE_DB, XP_COLLECTION, or ACHIEVEMENTS_COLLECTION")
# #             raise HTTPException(status_code=500, detail="Environment variables not set correctly.")

# #         print(f"🔍 Checking achievements for user: {request.user_id}")

# #         # Get user's XP documents
# #         try:
# #             xp_docs = databases.list_documents(
# #                 database_id=db_id,
# #                 collection_id=xp_collection,
# #                 queries=[Query.equal("user_id", request.user_id)]
# #             )
# #             print(f"📄 XP documents fetched: {xp_docs}")
# #         except AppwriteException as ae:
# #             print(f"🔥 Failed to fetch XP documents: {ae.message}, Code: {ae.code}, Response: {ae.response}")
# #             raise HTTPException(status_code=500, detail=f"Failed to fetch XP documents: {ae.message}")

# #         # Calculate total XP
# #         total_xp = sum(doc.get("xp", 0) for doc in xp_docs.get("documents", []))
# #         print(f"⚙️ Total XP for user {request.user_id}: {total_xp}")

# #         unlocked = []

# #         # Rule: unlock 'XP Master' if XP >= 50
# #         if total_xp >= 50:
# #             unlocked.append("XP Master")

# #         for title in unlocked:
# #             # Check for existing achievement
# #             try:
# #                 existing = databases.list_documents(
# #                     database_id=db_id,
# #                     collection_id=achievements_collection,
# #                     queries=[
# #                         Query.equal("user_id", request.user_id),
# #                         Query.equal("achievement", title)
# #                     ]
# #                 )
# #                 print(f"🔎 Checked existing achievements for {title}: {existing}")
# #             except AppwriteException as ae:
# #                 print(f"🔥 Failed to check existing achievements: {ae.message}, Code: {ae.code}, Response: {ae.response}")
# #                 raise HTTPException(status_code=500, detail=f"Failed to check achievements: {ae.message}")

# #             if not existing.get("documents", []):
# #                 print(f"🏆 Unlocking new achievement for user {request.user_id}: {title}")
# #                 try:
# #                     databases.create_document(
# #                         database_id=db_id,
# #                         collection_id=achievements_collection,
# #                         document_id=str(uuid.uuid4()),
# #                         data={
# #                             "user_id": request.user_id,
# #                             "achievement": title,
# #                             "timestamp": datetime.utcnow().isoformat()
# #                         }
# #                     )
# #                     print(f"✅ Achievement created: {title}")
# #                 except AppwriteException as ae:
# #                     print(f"🔥 Failed to create achievement: {ae.message}, Code: {ae.code}, Response: {ae.response}")
# #                     raise HTTPException(status_code=500, detail=f"Failed to create achievement: {ae.message}")
# #             else:
# #                 print(f"✅ Achievement already unlocked: {title}")

# #         return {"unlocked": unlocked}

# #     except AppwriteException as ae:
# #         print(f"🔥 Appwrite error: {ae.message}, Code: {ae.code}, Response: {ae.response}")
# #         raise HTTPException(status_code=500, detail=f"Appwrite error: {ae.message}")
# #     except Exception as e:
# #         print(f"💥 Unexpected error: {str(e)}")
# #         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# from fastapi import APIRouter, HTTPException
# from achievements.models import AchievementRequest
# from achievements.appwrite_client import databases
# from appwrite.query import Query
# from appwrite.exception import AppwriteException
# from datetime import datetime
# import os, uuid, requests

# router = APIRouter()

# # Helper function to fetch XP documents via HTTP request
# import urllib.parse

# def fetch_xp_documents(user_id: str):
#     url = f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('XP_COLLECTION')}/documents"
#     headers = {
#         "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT_ID"),
#         "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY")
#     }

#     # ✅ Proper Appwrite query string
#     query_string = f'equal("user_id", "{user_id}")'
#     params = {
#         "queries[]": query_string
#     }

#     # Send GET request with correct query syntax
#     res = requests.get(url, headers=headers, params=params)
#     if not res.ok:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to fetch XP documents: {res.text}"
#         )
#     return res.json()


# @router.post("/check")
# # def check_achievements(request: AchievementRequest):
# #     try:
# #         print("🚀 Received /check request for:", request.user_id)

# #         xp_docs = databases.list_documents(
# #             database_id=os.getenv("APPWRITE_DB"),
# #             collection_id=os.getenv("XP_COLLECTION"),
# #             queries=[
# #                 Query.equal("user_id", [request.user_id])
# #             ]
# #         )

# #         print("📄 XP documents fetched:", xp_docs)

# #         total_xp = sum(doc.get("xp_value", 0) for doc in xp_docs["documents"])
# #         unlocked = []

# #         if total_xp >= 50:
# #             unlocked.append("XP Master")

# #         for title in unlocked:
# #             exists = databases.list_documents(
# #                 database_id=os.getenv("APPWRITE_DB"),
# #                 collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                 queries=[
# #                     Query.equal("user_id", [request.user_id]),
# #                     Query.equal("achievement", [title])
# #                 ]
# #             )
# #             if not exists["documents"]:
# #                 databases.create_document(
# #                     database_id=os.getenv("APPWRITE_DB"),
# #                     collection_id=os.getenv("ACHIEVEMENTS_COLLECTION"),
# #                     document_id=str(uuid.uuid4()),
# #                     data={
# #                         "user_id": request.user_id,
# #                         "achievement": title,
# #                         "timestamp": datetime.utcnow().isoformat()
# #                     }
# #                 )

# #         return {"unlocked": unlocked}

# #     except AppwriteException as e:
# #         print("🔥 Appwrite error:", str(e))
# #         raise HTTPException(status_code=500, detail=f"Appwrite error: {str(e)}")

# #     except Exception as e:
# #         print("🔥 Unexpected error:", str(e))
# #         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# @router.post("/check")
# def check_achievements(request: AchievementRequest):
#     try:
#         print("🚀 Received /check request for:", request.user_id)

#         # Use REST API to query XP documents instead of SDK
#         res = requests.get(
#             f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('XP_COLLECTION')}/documents",
#             headers={
#                 "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT"),
#                 "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
#                 "Content-Type": "application/json"
#             },
#             params={
#                 "queries[]": f'equal("user_id", ["{request.user_id}"])'
#             }
#         )

#         if res.status_code != 200:
#             raise Exception(f"Failed to fetch XP documents: {res.text}")

#         xp_docs = res.json()["documents"]
#         print("📄 XP documents fetched:", xp_docs)

#         total_xp = sum(doc.get("xp_value", 0) for doc in xp_docs)
#         unlocked = []

#         if total_xp >= 50:
#             unlocked.append("XP Master")

#         # Repeat this raw approach for checking & inserting achievements
#         for title in unlocked:
#             res_check = requests.get(
#                 f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
#                 headers={
#                     "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT"),
#                     "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
#                 },
#                 params={
#                     "queries[]": f'equal("user_id", ["{request.user_id}"])',
#                     "queries[]": f'equal("achievement", ["{title}"])'
#                 }
#             )

#             if res_check.status_code != 200:
#                 raise Exception(f"Check failed: {res_check.text}")

#             if not res_check.json()["documents"]:
#                 res_create = requests.post(
#                     f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
#                     headers={
#                         "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT"),
#                         "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
#                         "Content-Type": "application/json"
#                     },
#                     json={
#                         "documentId": str(uuid.uuid4()),
#                         "data": {
#                             "user_id": request.user_id,
#                             "achievement": title,
#                             "timestamp": datetime.utcnow().isoformat()
#                         }
#                     }
#                 )
#                 if res_create.status_code != 201:
#                     raise Exception(f"Create failed: {res_create.text}")

#         return {"unlocked": unlocked}

#     except Exception as e:
#         print("🔥 Unexpected error:", str(e))
#         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# from fastapi import APIRouter, HTTPException
# from achievements.models import AchievementRequest
# from datetime import datetime
# import os, uuid, requests
# from urllib.parse import quote

# router = APIRouter()

# def make_appwrite_headers():
#     return {
#         "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT_ID"),
#         "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
#         "Content-Type": "application/json"
#     }

# @router.post("/check")
# def check_achievements(request: AchievementRequest):
#     try:
#         # 1. Fetch all XP documents for the user
#         xp_query = quote(f'equal("user_id", "{request.user_id}")', safe='')
#         xp_res = requests.get(
#             f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('XP_COLLECTION')}/documents",
#             headers=make_appwrite_headers(),
#             params={"queries[]": [xp_query]},
#             timeout=5  # Timeout added
#         )
        
#         if xp_res.status_code != 200:
#             return {"error": f"Failed to fetch XP: {xp_res.status_code} {xp_res.text}"}
        
#         xp_docs = xp_res.json().get("documents", [])
#         total_xp = sum(int(doc.get("xp_value", 0)) for doc in xp_docs)
#         unlocked = []
        
#         if total_xp >= 50:
#             unlocked.append("XP Master")
        
#         # 2. Process each unlocked achievement
#         for title in unlocked:
#             # Check if achievement already exists
#             achievement_queries = [
#                 quote(f'equal("user_id", "{request.user_id}")', safe=''),
#                 quote(f'equal("achievement", "{title}")', safe='')
#             ]
#             check_res = requests.get(
#                 f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
#                 headers=make_appwrite_headers(),
#                 params={"queries[]": achievement_queries},
#                 timeout=5  # Timeout added
#             )
            
#             if check_res.status_code != 200:
#                 continue  # Skip on error
            
#             existing = check_res.json().get("documents", [])
#             if not existing:
#                 # Create new achievement
#                 create_res = requests.post(
#                     f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
#                     headers=make_appwrite_headers(),
#                     json={
#                         "documentId": str(uuid.uuid4()),
#                         "data": {
#                             "user_id": request.user_id,
#                             "achievement": title,
#                             "timestamp": datetime.utcnow().isoformat() + "Z"
#                         }
#                     },
#                     timeout=5  # Timeout added
#                 )
#                 if create_res.status_code not in (200, 201):
#                     print(f"Failed to create achievement: {create_res.text}")
        
#         return {"unlocked": unlocked}

#     except requests.exceptions.Timeout:
#         raise HTTPException(status_code=504, detail="Request to Appwrite timed out")
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

from fastapi import APIRouter, HTTPException
from achievements.models import AchievementRequest
from datetime import datetime
import os, uuid, requests

router = APIRouter()

def make_appwrite_headers():
    return {
        "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT_ID"),
        "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
        "Content-Type": "application/json"
    }

@router.post("/check")
def check_achievements(request: AchievementRequest):
    try:
        # 1. Fetch all XP documents for the user using filters
        params = {
            "filters[user_id]": request.user_id
        }
        
        xp_res = requests.get(
            f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('XP_COLLECTION')}/documents",
            headers=make_appwrite_headers(),
            params=params,
            timeout=5
        )
        
        if xp_res.status_code != 200:
            return {"error": f"Failed to fetch XP: {xp_res.status_code} {xp_res.text}"}
        
        xp_docs = xp_res.json().get("documents", [])
        total_xp = sum(int(doc.get("xp_value", 0)) for doc in xp_docs)
        unlocked = []
        
        if total_xp >= 50:
            unlocked.append("XP Master")
        
        # 2. Process each unlocked achievement
        for title in unlocked:
            # Check if achievement already exists using filters
            check_params = {
                "filters[user_id]": request.user_id,
                "filters[achievement]": title
            }
            
            check_res = requests.get(
                f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
                headers=make_appwrite_headers(),
                params=check_params,
                timeout=5
            )
            
            if check_res.status_code != 200:
                continue  # Skip on error
            
            existing = check_res.json().get("documents", [])
            if not existing:
                # Create new achievement
                create_res = requests.post(
                    f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
                    headers=make_appwrite_headers(),
                    json={
                        "documentId": str(uuid.uuid4()),
                        "data": {
                            "user_id": request.user_id,
                            "achievement": title,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    },
                    timeout=5
                )
                if create_res.status_code not in (200, 201):
                    print(f"Failed to create achievement: {create_res.text}")
        
        return {"unlocked": unlocked}

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Appwrite request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
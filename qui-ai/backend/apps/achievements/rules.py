from typing import List, Dict
from database import achievements_collection, user_achievements_collection

async def check_and_award_achievements(user_id: str, user_data: Dict) -> List[Dict]:
    all_achievements = await achievements_collection.find().to_list(length=None)
    existing = await user_achievements_collection.find_one({"user_id": user_id}) or {"achievements": []}
    already_earned = [a["name"] for a in existing["achievements"]]

    newly_awarded = []

    for ach in all_achievements:
        if ach["name"] in already_earned:
            continue

        # Dynamic field match
        condition_field = ach["condition_type"]
        condition_value = ach["condition_value"]

        user_value = user_data.get(condition_field, 0)
        if user_value >= condition_value:
            newly_awarded.append(ach)

    if newly_awarded:
        await user_achievements_collection.update_one(
            {"user_id": user_id},
            {"$push": {"achievements": {"$each": newly_awarded}}},
            upsert=True
        )

    return newly_awarded

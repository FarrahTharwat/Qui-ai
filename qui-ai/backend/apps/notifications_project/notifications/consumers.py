import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_group = f"user_{self.scope['user'].id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.send(text_data=json.dumps({"message": data["message"]}))

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({"message": event["message"]}))

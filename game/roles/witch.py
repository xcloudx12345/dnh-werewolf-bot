from game.roles.villager import Villager
from game.text_template import *


class Witch(Villager):
    # Witch can reborn a dead player 1 time in a game

    def __init__(self, interface, player_id, player_name):
        super().__init__(interface, player_id, player_name)
        self.power = 1
        self.curse_power = 1

    def get_power(self):
        return self.power

    def on_use_power(self):
        self.power = 0

    def get_curse_power(self):
        return self.curse_power

    def on_use_curse_power(self):
        self.curse_power = 0

    async def on_night(self):
        pass

    async def on_action(self, embed_data):
        await self.interface.send_text_to_channel(generate_before_voting_witch(), self.channel_name)
        await self.interface.send_embed_to_channel(embed_data, self.channel_name)

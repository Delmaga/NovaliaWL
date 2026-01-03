# cogs/bda.py
import discord
from discord.ext import commands
import aiosqlite
import asyncio

class BDACog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = set()

    async def get_bda_config(self, guild_id: str):
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT category_id, next_number FROM bda_config WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {"category_id": row[0], "next_number": row[1]}
            return {"category_id": None, "next_number": 1}

    async def update_bda_config(self, guild_id: str, category_id: str = None, next_number: int = None):
        config = await self.get_bda_config(guild_id)
        cat = category_id if category_id is not None else config["category_id"]
        num = next_number if next_number is not None else config["next_number"]
        async with aiosqlite.connect("royal_bot.db") as db:
            await db.execute(
                "INSERT INTO bda_config (guild_id, category_id, next_number) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET category_id = excluded.category_id, next_number = excluded.next_number",
                (guild_id, cat, num)
            )
            await db.commit()

    async def get_or_create_bda_channel(self, guild: discord.Guild, category_id: str = None):
        # Vérifier si "Assistance" existe déjà
        for channel in guild.voice_channels:
            if channel.name == "Assistance":
                return channel

        # Définir la catégorie
        category = None
        if category_id:
            category = guild.get_channel(int(category_id))
            if not isinstance(category, discord.CategoryChannel):
                category = None

        # Créer le salon
        return await guild.create_voice_channel("Assistance", category=category)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        config = await self.get_bda_config(str(member.guild.id))

        # Si rejoint "Assistance"
        if after.channel and after.channel.name == "Assistance":
            number = config["next_number"]
            await self.update_bda_config(str(member.guild.id), next_number=number + 1)

            # Récupérer la catégorie
            category = None
            if config["category_id"]:
                cat_obj = member.guild.get_channel(int(config["category_id"]))
                if isinstance(cat_obj, discord.CategoryChannel):
                    category = cat_obj

            # Créer le salon temporaire DANS LA CATÉGORIE
            temp_channel = await member.guild.create_voice_channel(
                f"Assistance {number}",
                category=category
            )
            self.temp_channels.add(temp_channel.id)

            # Déplacer le membre
            try:
                await member.move_to(temp_channel)
            except:
                pass

        # Supprimer salon vide
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                await asyncio.sleep(2)
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete()
                        self.temp_channels.discard(before.channel.id)
                    except:
                        pass

    @discord.app_commands.command(name="bda", description="Créer le salon racine 'Assistance'")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def bda(self, interaction: discord.Interaction):
        config = await self.get_bda_config(str(interaction.guild.id))
        channel = await self.get_or_create_bda_channel(interaction.guild, config["category_id"])
        await interaction.response.send_message(f"`✅ Salon 'Assistance' prêt : {channel.mention}`", ephemeral=False)

    @discord.app_commands.command(name="bda_categorie", description="Définir la catégorie pour les salons BDA")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def bda_categorie(self, interaction: discord.Interaction, catégorie: discord.CategoryChannel):
        await self.update_bda_config(str(interaction.guild.id), category_id=str(catégorie.id))
        await interaction.response.send_message(f"`✅ Catégorie BDA définie : {catégorie.name}`", ephemeral=False)

async def setup(bot):
    await bot.add_cog(BDACog(bot))
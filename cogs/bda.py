# cogs/bda.py
import discord
from discord.ext import commands
import aiosqlite
import asyncio

class BDACog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_channels = set()  # Pour éviter les doublons

    async def get_or_create_bda_channel(self, guild: discord.Guild):
        """Récupère ou crée le salon vocal 'Assistance'."""
        # Vérifier si le salon existe déjà
        for channel in guild.voice_channels:
            if channel.name == "Assistance":
                return channel

        # Créer le salon
        channel = await guild.create_voice_channel("Assistance")
        return channel

    async def get_next_assistance_number(self, guild_id: str):
        """Récupère le prochain numéro disponible (1, 2, 3, ...)."""
        async with aiosqlite.connect("royal_bot.db") as db:
            cursor = await db.execute(
                "SELECT next_number FROM bda_counter WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                next_num = row[0]
                await db.execute(
                    "UPDATE bda_counter SET next_number = ? WHERE guild_id = ?",
                    (next_num + 1, guild_id)
                )
            else:
                next_num = 1
                await db.execute(
                    "INSERT INTO bda_counter (guild_id, next_number) VALUES (?, ?)",
                    (guild_id, 2)
                )
            await db.commit()
            return next_num

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        # Si le membre rejoint le salon "Assistance"
        if after.channel and after.channel.name == "Assistance":
            guild = member.guild

            # Obtenir le prochain numéro
            number = await self.get_next_assistance_number(str(guild.id))

            # Créer le salon temporaire
            temp_channel = await guild.create_voice_channel(f"Assistance {number}")
            self.temp_channels.add(temp_channel.id)

            # Déplacer le membre
            try:
                await member.move_to(temp_channel)
            except:
                pass  # Ignore si impossible (déjà déplacé)

        # Supprimer les salons temporaires vides
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                # Attendre 2 secondes pour éviter les faux positifs
                await asyncio.sleep(2)
                if len(before.channel.members) == 0 and before.channel in guild.voice_channels:
                    try:
                        await before.channel.delete()
                        self.temp_channels.discard(before.channel.id)
                    except:
                        pass

    @discord.app_commands.command(name="bda", description="Configurer le système d'assistance vocale")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def bda(self, interaction: discord.Interaction):
        channel = await self.get_or_create_bda_channel(interaction.guild)
        await interaction.response.send_message(f"`✅ Salon d'assistance créé : {channel.mention}`", ephemeral=False)

# ========== MISE À JOUR DE LA BASE DE DONNÉES ==========
# Ajoute cette table dans utils/db.py :
# 
# CREATE TABLE IF NOT EXISTS bda_counter (
#     guild_id TEXT PRIMARY KEY,
#     next_number INTEGER DEFAULT 1
# );

async def setup(bot):
    await bot.add_cog(BDACog(bot))
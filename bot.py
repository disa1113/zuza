import discord
import os
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime
import asyncio
from datetime import timedelta

# ==================== НАСТРОЙКИ (ЗАПОЛНИТЕ ЭТО) ====================
TOKEN = 'ТОКЕН_ВСТАВИТЬ_ПРИ_ЗАПУСКЕ'

# ID КАНАЛОВ
STATS_CHANNEL_ID = 1491763349786984459     # ID канала для статистики
VOICE_CREATOR_ID = 1491773231835906139      # ID канала-создателя
WELCOME_CHANNEL_ID = 1491490669435551784     # 👈 ID канала для приветствий (УКАЖИТЕ СВОЙ!)
CONTROL_CHANNEL_ID = 1491779656653865000    # 👈 ID канала для кнопок управления (УКАЖИТЕ СВОЙ!)
PING_CHANNEL_ID = 1491763349786984459      # 👈 ID канала для уведомлений "бот жив"

# ID РОЛИ (КОТОРАЯ БУДЕТ ВЫДАВАТЬСЯ НОВЫМ)
DEFAULT_ROLE_ID = 1327427550762369075        # 👈 ID роли для новичков (УКАЖИТЕ СВОЮ!)

SERVER_NAME = "Zuza"
# ====================================================================

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
from flask import Flask
from threading import Thread

web_app = Flask('')

@web_app.route('/')
def home():
    return "✅ Бот Zuza работает 24/7!"

def run_web():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ====================================================================

# Включаем интенты
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Статистика
class Stats:
    def __init__(self):
        self.joins = 0
        self.leaves = 0
        self.last_hour = datetime.now().hour
    
    def reset_hourly(self):
        self.joins = 0
        self.leaves = 0
        self.last_hour = datetime.now().hour
    
    def add_join(self):
        self.joins += 1
    
    def add_leave(self):
        self.leaves += 1

stats = Stats()
temp_channels = {}

# ============ КНОПКИ УПРАВЛЕНИЯ КАНАЛОМ ============
class VoiceChannelControlView(View):
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.owner_id = owner_id
    
    async def get_channel(self):
        return bot.get_channel(self.channel_id)
    
    def is_owner_or_admin(self, interaction: discord.Interaction):
        return interaction.user.id == self.owner_id or interaction.user.guild_permissions.administrator
    
    @discord.ui.button(label="➕ +1", style=discord.ButtonStyle.green, emoji="➕")
    async def increase_limit(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель канала!", ephemeral=True)
            return
        channel = await self.get_channel()
        if channel:
            new_limit = min(channel.user_limit + 1, 99) if channel.user_limit > 0 else 2
            await channel.edit(user_limit=new_limit)
            await interaction.response.send_message(f"✅ Лимит: {new_limit if new_limit > 0 else '∞'}", ephemeral=True)
    
    @discord.ui.button(label="➖ -1", style=discord.ButtonStyle.red, emoji="➖")
    async def decrease_limit(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель канала!", ephemeral=True)
            return
        channel = await self.get_channel()
        if channel:
            current = channel.user_limit
            if current == 0:
                new_limit = 99
            elif current == 1:
                new_limit = 0
            else:
                new_limit = current - 1
            await channel.edit(user_limit=new_limit)
            await interaction.response.send_message(f"✅ Лимит: {new_limit if new_limit > 0 else '∞'}", ephemeral=True)
    
    @discord.ui.button(label="🔒 Закрыть", style=discord.ButtonStyle.secondary, emoji="🔒")
    async def lock_channel(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель!", ephemeral=True)
            return
        channel = await self.get_channel()
        if channel:
            await channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("🔒 Канал закрыт", ephemeral=True)
    
    @discord.ui.button(label="🔓 Открыть", style=discord.ButtonStyle.secondary, emoji="🔓")
    async def unlock_channel(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель!", ephemeral=True)
            return
        channel = await self.get_channel()
        if channel:
            await channel.set_permissions(interaction.guild.default_role, connect=True)
            await interaction.response.send_message("🔓 Канал открыт", ephemeral=True)
    
    @discord.ui.button(label="✏️ Название", style=discord.ButtonStyle.primary, emoji="✏️")
    async def rename_channel(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель!", ephemeral=True)
            return
        await interaction.response.send_message("📝 Введи новое название:", ephemeral=True)
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            channel = await self.get_channel()
            if channel:
                await channel.edit(name=msg.content[:50])
                await interaction.followup.send(f"✅ Название: {msg.content[:50]}", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Время вышло", ephemeral=True)
    
    @discord.ui.button(label="❌ Удалить", style=discord.ButtonStyle.danger, emoji="❌")
    async def delete_channel(self, interaction: discord.Interaction, button: Button):
        if not self.is_owner_or_admin(interaction):
            await interaction.response.send_message("❌ Только создатель!", ephemeral=True)
            return
        channel = await self.get_channel()
        if channel and len(channel.members) == 0:
            await interaction.response.send_message("🗑️ Удаляю...", ephemeral=True)
            await asyncio.sleep(2)
            await channel.delete()
            await interaction.message.delete()
        else:
            await interaction.response.send_message("❌ Канал не пуст!", ephemeral=True)

# ==================== СОБЫТИЯ БОТА ====================

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} запущен!')
    print(f'📊 Статистика в канал: {STATS_CHANNEL_ID}')
    print(f'🎤 Канал-создатель: {VOICE_CREATOR_ID}')
    print(f'👋 Приветствия: {WELCOME_CHANNEL_ID}')
    print(f'🎮 Управление: {CONTROL_CHANNEL_ID}')
    print(f'🟢 Пинг-канал: {PING_CHANNEL_ID}')
    
    # Запускаем задачи
    hourly_report.start()
    keep_alive_ping.start()

# ============ УВЕДОМЛЕНИЕ КАЖДЫЕ 5 МИНУТ "БОТ ЖИВ" ============
@tasks.loop(minutes=5)
async def keep_alive_ping():
    """Отправляет сообщение каждые 5 минут, чтобы ты знал что бот работает"""
    channel = bot.get_channel(PING_CHANNEL_ID)
    if channel:
        now = datetime.now().strftime('%H:%M:%S')
        embed = discord.Embed(
            description=f"🟢 **Бот активен** | {now}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Zuza Bot | Работает 24/7")
        await channel.send(embed=embed)
        print(f"🟢 Пинг отправлен в {now}")
    else:
        print(f"❌ Канал с ID {PING_CHANNEL_ID} не найден!")

@bot.event
async def on_member_join(member):
    """Новый участник"""
    current_hour = datetime.now().hour
    if stats.last_hour != current_hour:
        stats.reset_hourly()
    stats.add_join()
    
    # Выдаём роль
    role = member.guild.get_role(DEFAULT_ROLE_ID)
    if role:
        await member.add_roles(role)
    
    # Приветствие в канал
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"🎉 Добро пожаловать на {SERVER_NAME}!",
            description=f"Привет, {member.mention}! Рады тебя видеть 🚀",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Теперь нас {member.guild.member_count}")
        await welcome_channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    """Участник вышел"""
    current_hour = datetime.now().hour
    if stats.last_hour != current_hour:
        stats.reset_hourly()
    stats.add_leave()

@bot.event
async def on_voice_state_update(member, before, after):
    """Голосовые каналы"""
    global temp_channels
    
    if after.channel and after.channel.id == VOICE_CREATOR_ID:
        guild = member.guild
        category = after.channel.category
        channel_name = f'🎤 {member.name}\'s канал'
        
        new_channel = await guild.create_voice_channel(
            name=channel_name,
            category=category,
            user_limit=0
        )
        
        await new_channel.set_permissions(member, 
            connect=True, manage_channels=True,
            mute_members=True, deafen_members=True, move_members=True
        )
        
        temp_channels[new_channel.id] = {
            'owner_id': member.id,
            'channel_id': new_channel.id
        }
        
        await member.move_to(new_channel)
        
        # Отправляем панель управления
        control_channel = bot.get_channel(CONTROL_CHANNEL_ID)
        if control_channel:
            embed = discord.Embed(
                title=f"🎮 Управление: {channel_name}",
                description=f"Создатель: {member.mention}\nЛимит: ∞",
                color=discord.Color.blue()
            )
            view = VoiceChannelControlView(new_channel.id, member.id)
            await control_channel.send(embed=embed, view=view)
    
    # Удаляем пустые каналы
    for channel_id, info in list(temp_channels.items()):
        channel = bot.get_channel(channel_id)
        if channel and len(channel.members) == 0:
            await channel.delete()
            del temp_channels[channel_id]

# ============ ЧАСОВАЯ СТАТИСТИКА ============
@tasks.loop(hours=1)
async def hourly_report():
    now = datetime.now()
    channel = bot.get_channel(STATS_CHANNEL_ID)
    
    if not channel:
        return
    
    embed = discord.Embed(
        title="📊 Часовая статистика",
        description=f"**{now.strftime('%H:%M')}** | **{now.strftime('%d.%m.%Y')}**",
        color=discord.Color.blue(),
        timestamp=now
    )
    embed.add_field(name="📥 Зашло", value=f"**{stats.joins}**", inline=True)
    embed.add_field(name="📤 Вышло", value=f"**{stats.leaves}**", inline=True)
    embed.add_field(name="👥 Всего", value=f"**{channel.guild.member_count}**", inline=True)
    
    change = stats.joins - stats.leaves
    if change > 0:
        embed.add_field(name="📈 Изменение", value=f"+{change}", inline=True)
    elif change < 0:
        embed.add_field(name="📉 Изменение", value=f"{change}", inline=True)
    else:
        embed.add_field(name="➖ Изменение", value="0", inline=True)
    
    await channel.send(embed=embed)
    stats.reset_hourly()

@hourly_report.before_loop
async def before_hourly():
    await bot.wait_until_ready()
    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    await asyncio.sleep((next_hour - now).total_seconds())

# ============ КОМАНДЫ ============
@bot.command()
@commands.has_permissions(administrator=True)
async def stats_now(ctx):
    now = datetime.now()
    embed = discord.Embed(
        title=f"📊 Статистика на {now.strftime('%H:%M')}",
        color=discord.Color.green()
    )
    embed.add_field(name="📥 Зашло", value=f"**{stats.joins}**", inline=True)
    embed.add_field(name="📤 Вышло", value=f"**{stats.leaves}**", inline=True)
    embed.add_field(name="👥 Всего", value=f"**{ctx.guild.member_count}**", inline=True)
    await ctx.send(embed=embed)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    keep_alive()  # Запускаем веб-сервер для Render
    bot.run(TOKEN)
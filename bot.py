import discord
import os
import random
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime
import asyncio
from datetime import timedelta

# ==================== НАСТРОЙКИ (ЗАПОЛНИТЕ ЭТО) ====================
TOKEN = os.getenv('TOKEN')

# ID КАНАЛОВ
STATS_CHANNEL_ID = 1491763349786984459     # ID канала для статистики
VOICE_CREATOR_ID = 1491773231835906139      # ID канала-создателя
WELCOME_CHANNEL_ID = 1491490669435551784     # 👈 ID канала для приветствий
PING_CHANNEL_ID = 1491763349786984459       # 👈 ID канала для уведомлений "бот жив"

# ID РОЛИ (КОТОРАЯ БУДЕТ ВЫДАВАТЬСЯ НОВЫМ)
DEFAULT_ROLE_ID = 1327427550762369075        # 👈 ID роли для новичков

SERVER_NAME = "Zuza"
# ====================================================================

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
from flask import Flask
from threading import Thread

web_app = Flask('')

@web_app.route('/')
def home():
    return "✅ Бот Zuza работает 24/7!"

@web_app.route('/health')
def health():
    return "OK", 200

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
        
        # Отправляем панель управления в ЛС
        try:
            embed = discord.Embed(
                title=f"🎮 Управление каналом: {channel_name}",
                description=f"Твой голосовой канал создан!\n\n"
                            f"🔧 **Панель управления:**\n"
                            f"• ➕ +1 — увеличить лимит\n"
                            f"• ➖ -1 — уменьшить лимит\n"
                            f"• 🔒 Закрыть — закрыть канал\n"
                            f"• 🔓 Открыть — открыть канал\n"
                            f"• ✏️ Название — изменить название\n"
                            f"• ❌ Удалить — удалить канал",
                color=discord.Color.green()
            )
            view = VoiceChannelControlView(new_channel.id, member.id)
            await member.send(embed=embed, view=view)
            print(f"💌 Панель управления отправлена в ЛС {member.name}")
        except:
            print(f"❌ Не удалось отправить ЛС {member.name} (закрыты сообщения)")
    
    # Удаляем пустые каналы
    for channel_id, info in list(temp_channels.items()):
        channel = bot.get_channel(channel_id)
        if channel and len(channel.members) == 0:
            await channel.delete()
            del temp_channels[channel_id]
            print(f'🗑️ Удалён пустой канал {channel.name}')

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

# ============ ОСНОВНЫЕ КОМАНДЫ ============
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

# ============ КОМАНДЫ ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ ============
@bot.command()
@commands.has_permissions(administrator=True)
async def лс(ctx, user: discord.Member, *, message: str):
    """Отправить личное сообщение пользователю. Использование: !лс @пользователь текст"""
    try:
        await user.send(f"📨 **Сообщение от администрации сервера {ctx.guild.name}:**\n\n{message}\n\n*Ответить на это сообщение нельзя.*")
        await ctx.send(f"✅ Сообщение отправлено пользователю {user.mention}")
        print(f"📨 ЛС отправлено от {ctx.author} к {user}: {message}")
    except discord.Forbidden:
        await ctx.send(f"❌ Не удалось отправить сообщение {user.mention}. У пользователя закрыты личные сообщения.")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def лс_всем(ctx, *, message: str):
    """Отправить сообщение всем участникам сервера (ОСТОРОЖНО!)"""
    await ctx.send("⚠️ Начинаю рассылку... Это может занять время.")
    
    sent = 0
    failed = 0
    
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            await member.send(f"📢 **Объявление от администрации {ctx.guild.name}:**\n\n{message}")
            sent += 1
            await asyncio.sleep(0.5)
        except:
            failed += 1
    
    await ctx.send(f"✅ Рассылка завершена!\n📨 Отправлено: {sent}\n❌ Не доставлено: {failed}")

# ============ КОМАНДЫ ДЛЯ ПРОСТОГО ОБЩЕНИЯ ============
@bot.command()
async def привет(ctx):
    await ctx.send(f"Привет, {ctx.author.mention}! Рад тебя видеть на Zuza! 🎮")

@bot.command()
async def как_дела(ctx):
    responses = [
        "Отлично! А у тебя? 🚀",
        "Хорошо, играю с друзьями! 🎮", 
        "Супер! Жду новых тиммейтов! 🤝",
        "Классно! На сервере Zuza всегда весело! 😎"
    ]
    await ctx.send(random.choice(responses))

@bot.command()
async def помощь(ctx):
    embed = discord.Embed(
        title="🤖 Команды бота Zuza",
        description="Вот что я умею:",
        color=discord.Color.blue()
    )
    embed.add_field(name="📊 **!stats_now**", value="Показать статистику сервера", inline=False)
    embed.add_field(name="👋 **!привет**", value="Поздороваться с ботом", inline=False)
    embed.add_field(name="💬 **!как_дела**", value="Спросить как дела у бота", inline=False)
    embed.add_field(name="📨 **!лс @пользователь текст**", value="Отправить ЛС пользователю (только админы)", inline=False)
    embed.add_field(name="📢 **!лс_всем текст**", value="Отправить ЛС всем на сервере (только админы)", inline=False)
    embed.add_field(name="🎤 **Голосовые каналы**", value="Зайди в канал `🎤 создать-канал` для создания личной комнаты", inline=False)
    embed.set_footer(text="Zuza Bot | Найди тиммейтов и играй вместе!")
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    text = message.content.lower()
    
    # Реакция на упоминание бота
    if bot.user in message.mentions:
        await message.reply(f"Привет, {message.author.mention}! Напиши `!помощь` чтобы узнать что я умею! 🎮")
    
    # Реакция на простые фразы
    elif any(word in text for word in ["привет бот", "здарова бот", "хай бот", "здравствуй бот"]):
        await message.reply(f"Привет, {message.author.mention}! Чем могу помочь? 🎉")
    
    elif any(word in text for word in ["пока бот", "до свидания бот", "прощай бот"]):
        await message.reply(f"Пока, {message.author.mention}! Заходи ещё на Zuza! 👋")
    
    elif "спасибо бот" in text:
        await message.reply(f"Всегда пожалуйста, {message.author.mention}! 🤗")
    
    await bot.process_commands(message)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)

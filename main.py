import discord
from discord.ext import commands
import json
import os
import asyncio
from dotenv import load_dotenv
from pathlib import Path

# 🔐 .ENV
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path, override=True)

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise Exception("❌ No se encontró DISCORD_TOKEN en .env")

# 🤖 BOT
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

FILE = "datos.json"

# 🎮 CONFIG
LEVELUP_IMAGE = "https://i.postimg.cc/c4nPT4f0/Captura.png"

# 🔊 AUDIO
SOUND_FILE = "lvlup.mp3"


# 📁 CARGAR DATOS
def cargar():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {}

usuarios = cargar()


# 💾 GUARDAR DATOS
def guardar():
    with open(FILE, "w") as f:
        json.dump(usuarios, f, indent=4)


# 📊 EXP NECESARIA
def exp_necesaria(level):
    return level * 2


# 📊 BARRA PROGRESO
def barra(exp, max_exp, size=10):

    if max_exp <= 0:
        return "░" * size

    fill = int((exp / max_exp) * size)

    return "█" * fill + "░" * (size - fill)


# 🎖️ RANGOS
def get_rango(level):

    if level < 5:
        return "Aventurero"

    elif level < 10:
        return "Rango Bronce"

    elif level < 20:
        return "Rango Plata"

    elif level < 40:
        return "Rango Oro"

    elif level < 75:
        return "Rango Hermekita"

    else:
        return "Rango Verserk"


# 🎖️ ASIGNAR ROLES
async def asignar_rol(member, level):

    nombre = get_rango(level)

    rol = discord.utils.get(member.guild.roles, name=nombre)

    if rol:

        for r in member.roles:

            if r.name.startswith("Rango") or r.name == "Aventurero":

                try:
                    await member.remove_roles(r)
                except:
                    pass

        try:
            await member.add_roles(rol)
        except:
            pass


# 🔐 COMPROBAR NARRADOR
def tiene_rol_narrador(ctx):
    return any(r.name == "Narrador" for r in ctx.author.roles)


# 🔊 SONIDO LEVEL UP
async def play_levelup_sound(member):

    if not member.voice or not member.voice.channel:
        return

    vc = None

    try:

        # 🔗 conectar
        vc = await member.voice.channel.connect()

        # 🎵 reproducir audio
        audio = discord.FFmpegPCMAudio(
            SOUND_FILE,
            before_options="-nostdin",
            options="-vn"
        )

        vc.play(audio)

        # ⏳ esperar a que termine
        while vc.is_playing():
            await asyncio.sleep(0.3)

        # delay pequeño
        await asyncio.sleep(1)

    except Exception as e:
        print("VOICE ERROR:", e)

    finally:

        # ❌ desconectar
        if vc and vc.is_connected():
            await vc.disconnect()


# 🎮 AÑADIR EXP
async def add_exp(member, exp, channel):

    user_id = str(member.id)

    if user_id not in usuarios:
        usuarios[user_id] = {
            "exp": 0,
            "level": 1
        }

    usuarios[user_id]["exp"] += exp

    leveled_up = False

    old_level = usuarios[user_id]["level"]

    # ⭐ subir niveles
    while usuarios[user_id]["exp"] >= exp_necesaria(usuarios[user_id]["level"]):

        usuarios[user_id]["exp"] -= exp_necesaria(
            usuarios[user_id]["level"]
        )

        usuarios[user_id]["level"] += 1

        leveled_up = True

    new_level = usuarios[user_id]["level"]

    guardar()

    # 🎖️ actualizar rol
    await asignar_rol(member, new_level)

    # 🎉 LEVEL UP
    if leveled_up:

        max_exp = exp_necesaria(new_level)

        # 📊 MENSAJE PROGRESO
        msg = await channel.send(
            f"📊 LEVEL UP!\n"
            f"👤 {member.mention}\n"
            f"⭐ {old_level} ➜ {new_level}\n"
            f"🔥 EXP: {usuarios[user_id]['exp']}/{max_exp}\n"
            f"{barra(usuarios[user_id]['exp'], max_exp)}"
        )

        await asyncio.sleep(1)

        await msg.edit(
            content="📊 Cargando... ████████████ 100%"
        )

        await asyncio.sleep(1)

        # 🔥 EMBED LEVEL UP
        embed = discord.Embed(
            title="🔥 LEVEL UP!",
            description=f"{member.name} subió a nivel {new_level}",
            color=discord.Color.gold()
        )

        embed.set_image(url=LEVELUP_IMAGE)

        embed.add_field(
            name="🎖️ Nuevo rango",
            value=get_rango(new_level),
            inline=False
        )

        embed.add_field(
            name="⭐ Nivel anterior",
            value=str(old_level),
            inline=False
        )

        await msg.edit(content=None, embed=embed)

        # 🔊 reproducir sonido
        await play_levelup_sound(member)


# ➕ COMANDO ADDXP
@bot.command()
async def addxp(ctx, member: discord.Member, exp: int):

    if not tiene_rol_narrador(ctx):

        await ctx.send("❌ No tienes permiso.")

        return

    await add_exp(member, exp, ctx.channel)

    user = usuarios[str(member.id)]

    max_exp = exp_necesaria(user["level"])

    await ctx.send(
        f"✅ +{exp} EXP a {member.mention}\n"
        f"⭐ Nivel: {user['level']}\n"
        f"🎖️ Rango: {get_rango(user['level'])}\n"
        f"🔥 EXP: {user['exp']}/{max_exp}\n"
        f"{barra(user['exp'], max_exp)}"
    )


# ➖ QUITAR EXP (LEVEL DOWN REAL)
@bot.command()
async def removexp(ctx, member: discord.Member, exp: int):

    if not tiene_rol_narrador(ctx):
        await ctx.send("❌ No tienes permiso.")
        return

    user_id = str(member.id)

    if user_id not in usuarios:
        await ctx.send("❌ Ese usuario no tiene datos.")
        return

    user = usuarios[user_id]

    # ➖ quitar exp
    user["exp"] -= exp

    # 🔻 bajar niveles correctamente
    while user["exp"] < 0 and user["level"] > 1:

        user["level"] -= 1

        # sumar exp del nivel anterior
        user["exp"] += exp_necesaria(user["level"])

    # evitar negativos absolutos
    if user["level"] == 1 and user["exp"] < 0:
        user["exp"] = 0

    guardar()

    # 🎖️ actualizar rol
    await asignar_rol(member, user["level"])

    max_exp = exp_necesaria(user["level"])

    await ctx.send(
        f"➖ Se quitaron {exp} EXP a {member.mention}\n"
        f"⭐ Nivel: {user['level']}\n"
        f"🎖️ Rango: {get_rango(user['level'])}\n"
        f"🔥 EXP: {user['exp']}/{max_exp}\n"
        f"{barra(user['exp'], max_exp)}"
    )


# 👀 VER NIVEL
@bot.command()
async def nivel(ctx, member: discord.Member = None):

    member = member or ctx.author

    user_id = str(member.id)

    if user_id not in usuarios:

        await ctx.send("📊 Sin nivel aún.")

        return

    user = usuarios[user_id]

    max_exp = exp_necesaria(user["level"])

    await ctx.send(
        f"📊 {member.mention}\n"
        f"⭐ Nivel: {user['level']}\n"
        f"🎖️ Rango: {get_rango(user['level'])}\n"
        f"🔥 EXP: {user['exp']}/{max_exp}\n"
        f"{barra(user['exp'], max_exp)}"
    )


# 🤖 BOT LISTO
@bot.event
async def on_ready():

    print(f"✅ Bot conectado como {bot.user}")


# 🚀 INICIAR BOT
bot.run(TOKEN)
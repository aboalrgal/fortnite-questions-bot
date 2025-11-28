# bot.py
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from discord import app_commands

import asyncio
import random
import difflib
from collections import defaultdict

# ==============================
# إعداد التوكن و الإنتنتس
# ==============================

BOT_TOKEN = os.getenv("TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "❌ متغيّر البيئة TOKEN غير موجود.\n"
        "اضبطه في Railway أو على جهازك على توكن البوت."
    )

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==============================
# ملفات JSON
# ==============================

SCORES_FILE = Path("scores.json")
QUESTIONS_FILE = Path("questions.json")

scores: Dict[int, int] = defaultdict(int)
questions: List[Dict] = []

# ==============================
# تحميل / حفظ النقاط
# ==============================

def load_scores() -> None:
    global scores
    if not SCORES_FILE.exists():
        print("⚠️ لا يوجد ملف scores.json، سيتم إنشاؤه لاحقاً.")
        return

    try:
        with SCORES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        for user_id_str, points in data.items():
            try:
                uid = int(user_id_str)
                scores[uid] = int(points)
            except ValueError:
                print(f"⚠️ تجاهل قيمة غير صحيحة في scores.json: {user_id_str} -> {points}")

        print(f"✅ تم تحميل {len(scores)} لاعب من scores.json")
    except Exception as e:
        print(f"❌ خطأ أثناء قراءة scores.json: {e}")


def save_scores() -> None:
    try:
        data = {str(uid): points for uid, points in scores.items()}
        with SCORES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 تم حفظ النقاط في scores.json")
    except Exception as e:
        print(f"❌ خطأ أثناء حفظ scores.json: {e}")

# ==============================
# تحميل / حفظ الأسئلة
# ==============================

def load_questions() -> None:
    global questions
    if not QUESTIONS_FILE.exists():
        print("⚠️ لا يوجد ملف questions.json، تأكد من إنشائه.")
        questions = []
        return

    try:
        with QUESTIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            questions = data
        else:
            print("❌ شكل questions.json غير صحيح (يجب أن يكون قائمة).")
            questions = []

        print(f"✅ تم تحميل {len(questions)} سؤال من questions.json")
    except Exception as e:
        print(f"❌ خطأ أثناء قراءة questions.json: {e}")
        questions = []


def save_questions() -> None:
    try:
        with QUESTIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print("💾 تم حفظ التعديلات على questions.json")
    except Exception as e:
        print(f"❌ خطأ أثناء حفظ questions.json: {e}")

# ==============================
# دوال مساعدة
# ==============================

def normalize_text(text: str) -> str:
    return text.strip().lower()


def is_answer_correct(user_answer: str, valid_answers: List[str], threshold: float = 0.75) -> bool:
    user_answer_norm = normalize_text(user_answer)

    for ans in valid_answers:
        ans_norm = normalize_text(ans)

        if user_answer_norm == ans_norm:
            return True

        if ans_norm in user_answer_norm or user_answer_norm in ans_norm:
            return True

        similarity = difflib.SequenceMatcher(None, user_answer_norm, ans_norm).ratio()
        if similarity >= threshold:
            return True

    return False


def format_leaderboard(scores_dict: Dict[int, int], guild: discord.Guild) -> str:
    if not scores_dict:
        return "🚫 لا يوجد أي مشاركات حتى الآن."

    sorted_scores = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)

    lines = []
    rank = 1
    for user_id, points in sorted_scores:
        member = guild.get_member(user_id)
        name = member.display_name if member else f"مستخدم ({user_id})"
        lines.append(f"**{rank}. {name}** — {points} نقطة")
        rank += 1

    return "🏆 **ترتيب المشاركين في تحدي الشتاء:**\n\n" + "\n".join(lines)

# ==============================
# حالة التحديات النشطة
# ==============================

active_challenges: Dict[int, bool] = {}  # channel_id -> bool

# ==============================
# منطق التحدي (مشترك لـ slash + text)
# ==============================

async def start_winter_challenge(channel: discord.TextChannel, user: discord.abc.User) -> None:
    channel_id = channel.id

    if active_challenges.get(channel_id, False):
        await channel.send("❄️ فيه سؤال شغال حالياً في هذه القناة، جاوب عليه أولاً قبل ما نبدأ سؤال جديد.")
        return

    if not questions:
        await channel.send("⚠️ لا توجد أسئلة حالياً. راجع ملف questions.json أو استخدم أوامر الإدارة.")
        return

    active_challenges[channel_id] = True

    question_data = random.choice(questions)
    question_text = question_data.get("question", "سؤال غير معروف 🤔")
    valid_answers = question_data.get("answers", [])

    await channel.send(
        f"❄️ **تحدي الشتاء بدأ!**\n"
        f"يا {user.mention} جاوب على السؤال التالي خلال **30 ثانية**:\n\n"
        f"🧠 **السؤال:** {question_text}"
    )

    def check(m: discord.Message) -> bool:
        return (
            m.channel.id == channel_id
            and m.author.id == user.id
            and not m.author.bot
        )

    try:
        reply: discord.Message = await bot.wait_for("message", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await channel.send(
            f"⌛ انتهى الوقت يا {user.mention}! تأخرت في الإجابة.\n"
            "تقدر تكتب `ابدا تحدي الشتاء` أو تستخدم `/winter_start` عشان تحاول مرة ثانية."
        )
        active_challenges[channel_id] = False
        return

    user_answer = reply.content

    if is_answer_correct(user_answer, valid_answers):
        scores[user.id] += 1
        save_scores()
        points = scores[user.id]
        await channel.send(
            f"✅ إجابة **صحيحة** يا {user.mention}! 🎉\n"
            f"رصيدك الآن: **{points}** نقطة."
        )
    else:
        correct_example = valid_answers[0] if valid_answers else "—"
        await channel.send(
            f"❌ إجابة **غير صحيحة** يا {user.mention}.\n"
            f"مثال لإجابة صحيحة: **{correct_example}**"
        )

    active_challenges[channel_id] = False

# ==============================
# EVENTS
# ==============================

@bot.event
async def on_ready():
    load_scores()
    load_questions()

    try:
        # مزامنة Slash Commands مع ديسكورد
        await bot.tree.sync()
        print("✅ تم مزامنة Slash Commands.")
    except Exception as e:
        print(f"⚠️ لم يتم مزامنة Slash Commands: {e}")

    print(f"✅ تم تسجيل الدخول كبوت: {bot.user} (ID: {bot.user.id})")
    print("جاهز لتحدي الشتاء! ❄️")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    if content == "ابدا تحدي الشتاء":
        if isinstance(message.channel, discord.TextChannel):
            await start_winter_challenge(message.channel, message.author)

    elif content == "ترتيب؟":
        if message.guild is not None:
            leaderboard_text = format_leaderboard(scores, message.guild)
            await message.channel.send(leaderboard_text)
        else:
            await message.channel.send("هذا الأمر يعمل داخل السيرفر فقط.")

    await bot.process_commands(message)

# ==============================
# Slash Commands ( / )
# ==============================

# /winter_start
@bot.tree.command(name="winter_start", description="ابدأ سؤال عشوائي من تحدي الشتاء")
async def winter_start(interaction: discord.Interaction):
    if interaction.channel is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("هذا الأمر يعمل في قنوات النص داخل السيرفر فقط.", ephemeral=True)
        return

    await interaction.response.defer()
    await start_winter_challenge(interaction.channel, interaction.user)

# /winter_rank
@bot.tree.command(name="winter_rank", description="عرض ترتيب المشاركين في تحدي الشتاء")
async def winter_rank(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
        return

    leaderboard_text = format_leaderboard(scores, interaction.guild)
    await interaction.response.send_message(leaderboard_text)

# -------- أوامر إدارية Slash --------

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator if interaction.guild else False

# /winter_add_question
@bot.tree.command(name="winter_add_question", description="إضافة سؤال جديد لتحدي الشتاء (أدمن فقط)")
@app_commands.describe(
    question="نص السؤال",
    answers="كل الإجابات الصحيحة مفصولة بـ ; مثال: الرياض;رياض"
)
async def winter_add_question(interaction: discord.Interaction, question: str, answers: str):
    if not is_admin(interaction):
        await interaction.response.send_message("هذا الأمر للأدمن فقط.", ephemeral=True)
        return

    answers_list = [a.strip() for a in answers.split(";") if a.strip()]

    if not question or not answers_list:
        await interaction.response.send_message("تأكد إنك كتبت السؤال والإجابات بشكل صحيح.", ephemeral=True)
        return

    new_q = {"question": question, "answers": answers_list}
    questions.append(new_q)
    save_questions()

    await interaction.response.send_message(
        f"✅ تم إضافة السؤال:\n**{question}**\n"
        f"عدد الإجابات المحتملة: **{len(answers_list)}**",
        ephemeral=True
    )

# /winter_list_questions
@bot.tree.command(name="winter_list_questions", description="عرض قائمة الأسئلة (أدمن فقط)")
async def winter_list_questions(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("هذا الأمر للأدمن فقط.", ephemeral=True)
        return

    if not questions:
        await interaction.response.send_message("⚠️ لا توجد أسئلة حالياً.", ephemeral=True)
        return

    lines = []
    for idx, q in enumerate(questions, start=1):
        qt = q.get("question", "—")
        lines.append(f"{idx}. {qt}")

    msg = "\n".join(lines)
    if len(msg) > 1900:
        await interaction.response.send_message(
            "عدد الأسئلة كبير، الأفضل تعدّلها مباشرة من ملف `questions.json`.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message("📋 **قائمة الأسئلة:**\n" + msg, ephemeral=True)

# /winter_delete_question
@bot.tree.command(name="winter_delete_question", description="حذف سؤال برقم من القائمة (أدمن فقط)")
@app_commands.describe(index="رقم السؤال كما يظهر في قائمة الأسئلة (1، 2، 3، ...)")
async def winter_delete_question(interaction: discord.Interaction, index: int):
    if not is_admin(interaction):
        await interaction.response.send_message("هذا الأمر للأدمن فقط.", ephemeral=True)
        return

    if not questions:
        await interaction.response.send_message("⚠️ لا توجد أسئلة لحذفها.", ephemeral=True)
        return

    if index < 1 or index > len(questions):
        await interaction.response.send_message("⚠️ رقم السؤال غير صحيح.", ephemeral=True)
        return

    removed = questions.pop(index - 1)
    save_questions()

    await interaction.response.send_message(
        f"🗑 تم حذف السؤال:\n**{removed.get('question', '—')}**",
        ephemeral=True
    )

# /winter_reload_questions
@bot.tree.command(name="winter_reload_questions", description="إعادة تحميل questions.json من جديد (أدمن فقط)")
async def winter_reload_questions(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("هذا الأمر للأدمن فقط.", ephemeral=True)
        return

    load_questions()
    await interaction.response.send_message(
        f"✅ تم إعادة تحميل الأسئلة. العدد الحالي: **{len(questions)}** سؤال.",
        ephemeral=True
    )

# /winter_reset_scores
@bot.tree.command(name="winter_reset_scores", description="تصفير النقاط (الكل أو شخص واحد) (أدمن فقط)")
@app_commands.describe(
    user="اختياري: مستخدم معيّن لتصفير نقاطه فقط. لو تركته فاضي يصفر نقاط الجميع."
)
async def winter_reset_scores(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    if not is_admin(interaction):
        await interaction.response.send_message("هذا الأمر للأدمن فقط.", ephemeral=True)
        return

    global scores

    if user is None:
        scores = defaultdict(int)
        save_scores()
        await interaction.response.send_message("✅ تم تصفير نقاط جميع المشاركين.", ephemeral=True)
    else:
        if user.id in scores:
            scores[user.id] = 0
            save_scores()
            await interaction.response.send_message(
                f"✅ تم تصفير نقاط {user.mention}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ هذا المستخدم ما عنده نقاط مسجلة.",
                ephemeral=True
            )

# ==============================
# أوامر Prefix (القديمة) للإدارة
# ==============================

@bot.command(name="اضف_سؤال")
@commands.has_permissions(administrator=True)
async def add_question_cmd(ctx: commands.Context, *, data: str):
    """
    مثال:
    !اضف_سؤال ما هي عاصمة قطر؟ | الدوحة ; دوحة
    """
    if "|" not in data:
        await ctx.send("⚠️ الصيغة غير صحيحة.\nاستخدم: `!اضف_سؤال السؤال | جواب1 ; جواب2 ; ...`")
        return

    question_text, answers_part = map(str.strip, data.split("|", 1))
    answers_list = [a.strip() for a in answers_part.split(";") if a.strip()]

    if not question_text or not answers_list:
        await ctx.send("⚠️ تأكد من السؤال والإجابات.")
        return

    new_q = {"question": question_text, "answers": answers_list}
    questions.append(new_q)
    save_questions()
    await ctx.send(f"✅ تم إضافة السؤال:\n**{question_text}**")


@bot.command(name="الأسئلة")
@commands.has_permissions(administrator=True)
async def list_questions_cmd(ctx: commands.Context):
    if not questions:
        await ctx.send("⚠️ لا توجد أسئلة حالياً.")
        return

    lines = []
    for idx, q in enumerate(questions, start=1):
        qt = q.get("question", "—")
        lines.append(f"{idx}. {qt}")

    msg = "\n".join(lines)
    if len(msg) > 1900:
        await ctx.send("⚠️ عدد الأسئلة كبير، عدّل من `questions.json` مباشرة.")
    else:
        await ctx.send("📋 **قائمة الأسئلة:**\n" + msg)


@bot.command(name="حذف_سؤال")
@commands.has_permissions(administrator=True)
async def delete_question_cmd(ctx: commands.Context, index: int):
    if not questions:
        await ctx.send("⚠️ لا توجد أسئلة.")
        return

    if index < 1 or index > len(questions):
        await ctx.send("⚠️ رقم السؤال غير صحيح.")
        return

    removed = questions.pop(index - 1)
    save_questions()
    await ctx.send(f"🗑 تم حذف السؤال:\n**{removed.get('question', '—')}**")


@bot.command(name="إعادة_تحميل_الأسئلة")
@commands.has_permissions(administrator=True)
async def reload_questions_cmd(ctx: commands.Context):
    load_questions()
    await ctx.send(f"✅ تم إعادة تحميل الأسئلة. العدد الحالي: **{len(questions)}** سؤال.")


@bot.command(name="تصفير_النقاط")
@commands.has_permissions(administrator=True)
async def reset_scores_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    global scores

    if member is None:
        scores = defaultdict(int)
        save_scores()
        await ctx.send("✅ تم تصفير نقاط جميع المشاركين.")
    else:
        if member.id in scores:
            scores[member.id] = 0
            save_scores()
            await ctx.send(f"✅ تم تصفير نقاط {member.mention}.")
        else:
            await ctx.send("⚠️ هذا المستخدم ما عنده نقاط.")

# ==============================
# تشغيل البوت
# ==============================

if __name__ == "__main__":
    bot.run(BOT_TOKEN)


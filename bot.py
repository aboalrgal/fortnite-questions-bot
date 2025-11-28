# bot.py
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
import discord
from discord.ext import commands
import asyncio
import random
import difflib
from collections import defaultdict

# ==============================
# إعداد التوكن و الإنتنتس
# ==============================

# التوكن من متغير بيئة (مهم لـ Railway)
BOT_TOKEN = os.getenv("TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "❌ متغيّر البيئة TOKEN غير موجود.\n"
        "في Railway أو على جهازك، اضبط متغيّر البيئة TOKEN على توكن البوت."
    )

intents = discord.Intents.default()
intents.message_content = True  # مهم لقراءة محتوى الرسائل
intents.members = True          # مفيد لو استخدمنا معلومات الأعضاء لاحقاً

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==============================
# ملفات JSON
# ==============================

SCORES_FILE = Path("scores.json")
QUESTIONS_FILE = Path("questions.json")

scores: dict[int, int] = defaultdict(int)
questions: list[dict] = []  # كل عنصر: {"question": str, "answers": [str, ...]}


# ==============================
# دوال تحميل / حفظ النقاط
# ==============================

def load_scores():
    global scores
    if not SCORES_FILE.exists():
        print("⚠️ لا يوجد ملف scores.json، سيتم إنشاؤه عند أول حفظ نقاط.")
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

        print(f"✅ تم تحميل {len(scores)} لاعب/لاعبة من scores.json")
    except Exception as e:
        print(f"❌ خطأ أثناء قراءة scores.json: {e}")


def save_scores():
    try:
        data = {str(uid): points for uid, points in scores.items()}
        with SCORES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("💾 تم حفظ النقاط في scores.json")
    except Exception as e:
        print(f"❌ خطأ أثناء حفظ scores.json: {e}")


# ==============================
# دوال تحميل / حفظ الأسئلة
# ==============================

def load_questions():
    global questions
    if not QUESTIONS_FILE.exists():
        print("⚠️ لا يوجد ملف questions.json، تأكد من إنشائه وإضافة أسئلة.")
        questions = []
        return

    try:
        with QUESTIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # تأكد أن البيانات قائمة
        if isinstance(data, list):
            questions = data
        else:
            print("❌ شكل questions.json غير صحيح، يجب أن يكون قائمة (list).")
            questions = []

        print(f"✅ تم تحميل {len(questions)} سؤال من questions.json")
    except Exception as e:
        print(f"❌ خطأ أثناء قراءة questions.json: {e}")
        questions = []


def save_questions():
    """حفظ الأسئلة في questions.json (يُستخدم مع الأوامر الإدارية)."""
    try:
        with QUESTIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print("💾 تم حفظ التعديلات على questions.json")
    except Exception as e:
        print(f"❌ خطأ أثناء حفظ questions.json: {e}")


# ==============================
# دوال مساعدة منطقية
# ==============================

def normalize_text(text: str) -> str:
    return text.strip().lower()


def is_answer_correct(user_answer: str, valid_answers: list[str], threshold: float = 0.75) -> bool:
    user_answer_norm = normalize_text(user_answer)

    for ans in valid_answers:
        ans_norm = normalize_text(ans)

        # تطابق مباشر
        if user_answer_norm == ans_norm:
            return True

        # احتواء/جزء من
        if ans_norm in user_answer_norm or user_answer_norm in ans_norm:
            return True

        # تشابه تقريبي
        similarity = difflib.SequenceMatcher(None, user_answer_norm, ans_norm).ratio()
        if similarity >= threshold:
            return True

    return False


def format_leaderboard(scores_dict: dict[int, int], guild: discord.Guild) -> str:
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

active_challenges: dict[int, bool] = {}  # channel_id -> bool

# ==============================
# EVENTS
# ==============================

@bot.event
async def on_ready():
    load_scores()
    load_questions()
    print(f"✅ تم تسجيل الدخول كبوت: {bot.user} (ID: {bot.user.id})")
    print("جاهز لتحدي الشتاء! ❄️")


@bot.event
async def on_message(message: discord.Message):
    # تجاهل البوت نفسه
    if message.author.bot:
        return

    content = message.content.strip()

    # ==========================
    # بدء التحدي: "ابدا تحدي الشتاء"
    # ==========================
    if content == "ابدا تحدي الشتاء":
        channel_id = message.channel.id

        if active_challenges.get(channel_id, False):
            await message.channel.send("❄️ فيه سؤال شغال حالياً في هذه القناة، جاوب عليه أولاً قبل ما نبدأ سؤال جديد.")
            return

        if not questions:
            await message.channel.send("⚠️ لا توجد أسئلة حالياً. راجع ملف questions.json أو استخدم أوامر الإدارة.")
            return

        active_challenges[channel_id] = True

        question_data = random.choice(questions)
        question_text = question_data.get("question", "سؤال غير معروف 🤔")
        valid_answers = question_data.get("answers", [])

        await message.channel.send(
            f"❄️ **تحدي الشتاء بدأ!**\n"
            f"يا {message.author.mention} جاوب على السؤال التالي خلال **30 ثانية**:\n\n"
            f"🧠 **السؤال:** {question_text}"
        )

        def check(m: discord.Message) -> bool:
            return (
                m.channel.id == message.channel.id
                and m.author.id == message.author.id
                and not m.author.bot
            )

        try:
            reply: discord.Message = await bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await message.channel.send(
                f"⌛ انتهى الوقت يا {message.author.mention}! تأخرت في الإجابة.\n"
                "تقدر تكتب `ابدا تحدي الشتاء` عشان تحاول مرة ثانية."
            )
            active_challenges[channel_id] = False
            return

        user_answer = reply.content

        if is_answer_correct(user_answer, valid_answers):
            scores[message.author.id] += 1
            save_scores()
            points = scores[message.author.id]
            await message.channel.send(
                f"✅ إجابة **صحيحة** يا {message.author.mention}! 🎉\n"
                f"رصيدك الآن: **{points}** نقطة."
            )
        else:
            correct_example = valid_answers[0] if valid_answers else "—"
            await message.channel.send(
                f"❌ إجابة **غير صحيحة** يا {message.author.mention}.\n"
                f"مثال لإجابة صحيحة: **{correct_example}**"
            )

        active_challenges[channel_id] = False

    # ==========================
    # طلب الترتيب: "ترتيب؟"
    # ==========================
    elif content == "ترتيب؟":
        leaderboard_text = format_leaderboard(scores, message.guild)
        await message.channel.send(leaderboard_text)

    # مهم عشان تشتغل أوامر الـ commands
    await bot.process_commands(message)


# ==============================
# أوامر إدارية (للأدمن فقط)
# ==============================

# إضافة سؤال جديد: !اضف_سؤال السؤال | جواب1 ; جواب2 ; جواب3
@bot.command(name="اضف_سؤال")
@commands.has_permissions(administrator=True)
async def add_question(ctx: commands.Context, *, data: str):
    """
    مثال الاستخدام:
    !اضف_سؤال ما هي عاصمة قطر؟ | الدوحة ; دوحة
    """
    try:
        if "|" not in data:
            await ctx.send("⚠️ الصيغة غير صحيحة.\nاستخدم: `!اضف_سؤال السؤال | جواب1 ; جواب2 ; جواب3`")
            return

        question_text, answers_part = map(str.strip, data.split("|", 1))

        if not question_text or not answers_part:
            await ctx.send("⚠️ تأكد إن السؤال والإجابات مو فاضية.")
            return

        answers = [a.strip() for a in answers_part.split(";") if a.strip()]
        if not answers:
            await ctx.send("⚠️ لازم تضيف إجابة واحدة على الأقل.")
            return

        new_q = {"question": question_text, "answers": answers}
        questions.append(new_q)
        save_questions()

        await ctx.send(
            f"✅ تم إضافة السؤال:\n**{question_text}**\n"
            f"مع {len(answers)} إجابة/إجابات محتملة."
        )
    except Exception as e:
        await ctx.send(f"❌ صار خطأ أثناء إضافة السؤال: `{e}`")


# عرض قائمة مختصرة بالأسئلة: !الأسئلة
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

    # لو كثير، نقسمها
    msg = "\n".join(lines)
    if len(msg) > 1900:
        await ctx.send("⚠️ عدد الأسئلة كبير، عدّل مباشرة من ملف `questions.json`.")
    else:
        await ctx.send("📋 **قائمة الأسئلة:**\n" + msg)


# حذف سؤال برقم: !حذف_سؤال 3
@bot.command(name="حذف_سؤال")
@commands.has_permissions(administrator=True)
async def delete_question(ctx: commands.Context, index: int):
    if not questions:
        await ctx.send("⚠️ لا توجد أسئلة لحذفها.")
        return

    if index < 1 or index > len(questions):
        await ctx.send("⚠️ رقم السؤال غير صحيح.")
        return

    removed = questions.pop(index - 1)
    save_questions()

    await ctx.send(f"🗑 تم حذف السؤال:\n**{removed.get('question', '—')}**")


# إعادة تحميل الأسئلة من questions.json: !إعادة_تحميل_الأسئلة
@bot.command(name="إعادة_تحميل_الأسئلة")
@commands.has_permissions(administrator=True)
async def reload_questions_cmd(ctx: commands.Context):
    load_questions()
    await ctx.send(f"✅ تم إعادة تحميل الأسئلة. العدد الحالي: **{len(questions)}** سؤال.")


# تصفير نقاط شخص أو الكل
# !تصفير_النقاط  (يصفّر كل المشاركين)
# !تصفير_النقاط @مستخدم
@bot.command(name="تصفير_النقاط")
@commands.has_permissions(administrator=True)
async def reset_scores_cmd(ctx: commands.Context, member: discord.Member | None = None):
    global scores

    if member is None:
        # تصفير الكل
        scores = defaultdict(int)
        save_scores()
        await ctx.send("✅ تم تصفير نقاط جميع المشاركين.")
    else:
        if member.id in scores:
            scores[member.id] = 0
            save_scores()
            await ctx.send(f"✅ تم تصفير نقاط {member.mention}.")
        else:
            await ctx.send("⚠️ هذا المستخدم ما عنده نقاط مسجلة.")


# رسالة مساعدة بسيطة: !هلب
@bot.command(name="Help")
async def help_cmd(ctx: commands.Context):
    await ctx.send(
        "**قائمة الأوامر:**\n\n"
        "🧊 أوامر اللاعبين:\n"
        "`ابدا تحدي الشتاء` — يبدأ لك سؤال عشوائي من تحدي الشتاء.\n"
        "`ترتيب؟` — يعرض ترتيب المشاركين بالنقاط.\n\n"
        "🛠 أوامر إدارية (تحتاج أدمن):\n"
        "`!اضف_سؤال السؤال | جواب1 ; جواب2 ; ...`\n"
        "`!الأسئلة` — عرض قائمة الأسئلة بأرقامها.\n"
        "`!حذف_سؤال رقم` — حذف سؤال برقم.\n"
        "`!إعادة_تحميل_الأسئلة` — إعادة قراءة questions.json`\n"
        "`!تصفير_النقاط` — تصفير نقاط الجميع.\n"
        "`!تصفير_النقاط @مستخدم` — تصفير نقاط شخص واحد."
    )


# ==============================
# تشغيل البوت
# ==============================

if __name__ == "__main__":
    bot.run(BOT_TOKEN)


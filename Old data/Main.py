import discord
from discord.ext import commands
import random
import json
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
character_stats = {}
skill_data = {"shop": {}, "user_points": {}, "base_stamina": 0.0}
STATS_FILE = "character_stats.json"
SKILL_FILE = "skill_data.json"
ALLOWED_ROLE = "JRA"
multipliers = {
    'Start': {'Front': 1.3, 'Pace': 1.0, 'Late': 0.8, 'End': 0.6},
    'Mid': {'Front': 1.0, 'Pace': 0.8, 'Late': 1.0, 'End': 1.1},
    'Final': {'Front': 0.7, 'Pace': 1.2, 'Late': 1.2, 'End': 1.3}
}
MODIFIERS = {
    'g': 0.6,  # -40%
    'f': 0.7,  # -30%
    'e': 0.75,  # -25%
    'd': 0.8,  # -20%
    'c': 0.9,  # -10%
    'b': 1.0,  # 0%
    'a': 1.1,  # +10%
    's': 1.2  # +20%
}

@bot.event
async def on_ready():
    global character_stats, skill_data
    print(f'Bot is ready as {bot.user}')
    # Load character stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                character_stats = json.load(f)
                for name, stats in character_stats.items():
                    character_stats[name] = {
                        'Spd': float(stats.get('Spd', 0.0)),
                        'Sta': float(stats.get('Sta', 0.0)),
                        'Pow': float(stats.get('Pow', 0.0)),
                        'Gut': float(stats.get('Gut', 0.0)),
                        'Wit': float(stats.get('Wit', 0.0)),
                        'Surface': stats.get('Surface', 'B'),
                        'Distance': stats.get('Distance', 'B'),
                        'Strategy': stats.get('Strategy', 'B'),
                        'StartScore': float(stats.get('StartScore', 0.0)),
                        'MidScore': float(stats.get('MidScore', 0.0)),
                        'FinalScore': float(stats.get('FinalScore', 0.0)),
                        'MidTotalScore': float(stats.get('MidTotalScore', 0.0)),
                        'FinalTotalScore': float(stats.get('FinalTotalScore', 0.0)),
                        'Bracket': stats.get('Bracket', ''),
                        'Overflow': float(stats.get('Overflow', 0.0))
                    }
    except Exception as e:
        print(f"Error loading stats from file: {str(e)}")
        character_stats = {}
    try:
        if os.path.exists(SKILL_FILE):
            with open(SKILL_FILE, 'r') as f:
                skill_data = json.load(f)
                # Ensure structure
                if "shop" not in skill_data:
                    skill_data["shop"] = {}
                if "user_points" not in skill_data:
                    skill_data["user_points"] = {}
                if "base_stamina" not in skill_data:
                    skill_data["base_stamina"] = 0.0
                skill_data["base_stamina"] = float(skill_data["base_stamina"])
                # Convert shop to new format if necessary
                skill_data["shop"] = {
                    skill: {
                        "cost": float(data["cost"] if isinstance(data, dict) else data),
                        "emoji": data.get("emoji", "") if isinstance(data, dict) else ""
                    }
                    for skill, data in skill_data["shop"].items()
                }
                skill_data["user_points"] = {
                    str(k): {"points": float(v.get("points", 0.0)), "skills": v.get("skills", [])}
                    for k, v in skill_data["user_points"].items()
                }
    except Exception as e:
        print(f"Error loading skill data from file: {str(e)}")
        skill_data = {"shop": {}, "user_points": {}, "base_stamina": 0.0}


# Helper function to save character stats
def save_stats():
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(character_stats, f, indent=4)
    except Exception as e:
        print(f"Error saving stats to file: {str(e)}")


# Helper function to save skill data
def save_skill_data():
    try:
        with open(SKILL_FILE, 'w') as f:
            json.dump(skill_data, f, indent=4)
    except Exception as e:
        print(f"Error saving skill data to file: {str(e)}")


# Helper function to parse stats and apply modifiers
def parse_stats(spd, sta, pow, gut, wit, surface, distance, strategy):
    try:
        stats = {
            'Spd': float(spd),
            'Sta': float(sta),
            'Pow': float(pow),
            'Gut': float(gut),
            'Wit': float(wit)
        }
        surface = surface.lower()
        distance = distance.lower()
        strategy = strategy.lower()
        valid_modifiers = MODIFIERS.keys()
        if surface not in valid_modifiers:
            return None, f"Invalid Surface: '{surface}'. Must be one of: G, F, E, D, C, B, A, S"
        if distance not in valid_modifiers:
            return None, f"Invalid Distance: '{distance}'. Must be one of: G, F, E, D, C, B, A, S"
        if strategy not in valid_modifiers:
            return None, f"Invalid Strategy: '{strategy}'. Must be one of: G, F, E, D, C, B, A, S"
        stats['Spd'] *= MODIFIERS[distance]
        stats['Pow'] *= MODIFIERS[surface]
        stats['Wit'] *= MODIFIERS[strategy]
        stats['Surface'] = surface.upper()
        stats['Distance'] = distance.upper()
        stats['Strategy'] = strategy.upper()
        return stats, None
    except ValueError:
        return None, "All stats (Spd, Sta, Pow, Gut, Wit) must be numbers."

@bot.command()
async def Finehelp(ctx, *, subcommand=None):
    if subcommand and subcommand.strip().lower() == "shop":
        shop_help = (
            "**Hướng dẫn lệnh mua sắm cùng với Finechi**\n\n"
            "**!Fshop** - Xem hoặc mua kỹ năng từ shop\n"
            "- **Xem Shop**: Xem danh sách kỹ năng và chi phí.\n"
            "  Cú pháp: `!Fshop`\n"
            "  Ví dụ: `!Fshop`\n"
            "- **Setting Shop**: Thêm danh sách kỹ năng và chi phí (chỉ vai trò JRA).\n"
            "  Cú pháp: `!Fshop config \"<SkillName>\" <Cost> [\"<SkillName>\" <Cost> ...]`\n"
            "  Ví dụ: `!Fshop config \"Speed Boost\" 50 \"Stamina Surge\" 75`\n"
            "- **Mua Kỹ Năng**: Mua kỹ năng từ shop bằng điểm kỹ năng.\n"
            "  Cú pháp: `!Fshop buy \"<SkillName>\"`\n"
            "  Ví dụ: `!Fshop buy \"Speed Boost\"`\n"
            "- **Nuke Shop**: Xóa tất cả kỹ năng trong shop (chỉ vai trò JRA).\n"
            "  Cú pháp: `!Fshop clear`\n"
            "  Ví dụ: `!Fshop clear`"
        )
        await ctx.send(shop_help)
        return

    help_message_part1 = (
        "**Hướng dẫn ăn mì (lệnh bot) cùng Finechi**\n\n"
        "**!calc** - Quản lý chỉ số nhân vật hoặc tính toán.\n"
        "- **Nhập Chỉ Số**: Lưu chỉ số cho nhân vật.\n"
        "  Cú pháp: `!calc import <Name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>`\n"
        "  Ví dụ: `!calc import FineMotion 100 150 90 250 60 | A S S`\n"
        "  Lưu ý: Tên không được có cách và các mã nương phải viết đúng tên để dùng các lệnh cần nó bên dưới.\n"
        "- **Xóa Chỉ Số**: Xóa tất cả chỉ số đã lưu.\n"
        "  Cú pháp: `!calc reset`\n"
        "  Ví dụ: `!calc reset` hoặc `!calc reset <tên>`\n"
        "  (Nhưng chỉ Ramen Princess mới dùng được)\n"
        "- **Stamina check**:\n"
        "  Cú pháp: `!calc race <Name> <Base Stamina>`\n"
        "  Ví dụ: `!calc race FineMotion 360`\n"
        "- **Tính toán điểm đua (Không lưu)**:\n"
        "  Cú pháp: `!calc <loại> <Name> <X>` hoặc `!calc <Type> <Spd> <Sta> <Pow> <Gut> <Wit> <X>` (X là 1d10)\n"
        "  Ví dụ: `!calc StartFront FineMotion 10`\n"
        "  Lưu ý: Sử dụng loại như StartFront, MidPace, FinalLate.\n"
    )
    help_message_part2 = (
        "- **Lưu Điểm Số**: Tính và lưu điểm số cho giai đoạn đó.\n"
        "  Cú pháp: `!calc save <loại> <Name> <X>`\n"
        "  Ví dụ: `!calc save StartPace FineMotion 10`\n"
        "  Lưu ý: Lưu StartScore, MidScore, hoặc FinalScore dựa trên loại (Start/Mid/Final) và X vẫn là 1d10.\n"
        "**!Frace** - Quản lý đua.\n"
        "- **Unique Skill Input**: Boost thẳng stat với điểm khi kích unique/skill.\n"
        "  Cú pháp: `!Frace unique <Name> <Spd% or flat> <Sta% or flat> <Pow% or flat> <Gut% or flat> <Wit% or flat> <StartScore>`\n"
        "  Ví dụ: `!Frace unique FineMotion 10% 5 0 0 0 10`\n"
        "- **Đăng Ký Đua Nhóm**: Đăng ký một hoặc nhiều mã nương vào bảng A, B, hoặc C.\n"
        "  Cú pháp: `!Frace import <Name1> [<Name2> ...] <A/B/C>`\n"
        "  Ví dụ: `!Frace import FineMotion StillInLove A`\n"
        "- **Xem Bảng Xếp Hạng**: Hiển thị điểm số từ cao đến thấp trong bảng chỉ định.\n"
        "  Cú pháp: `!Frace <A/B/C>`\n"
        "  Ví dụ: `!Frace A`\n"
    )
    help_message_part3 = (
        "**!Froll <Y>** - Quay số ngẫu nhiên từ 1 đến Y\n"
        "  Cú pháp: `!Froll <Y>`\n"
        "  Ví dụ: `!Froll 100`\n\n"
        "**!Dueling** - Time to duel !!!, Perform dueling mechanic. Chi tiết hay xem cơ chế ở #race systems\n\n" 
        "**!skillpoint**\n"
        "- **Xem Điểm**: Xem pts và skill đã mua.\n"
        "  Cú pháp: `!skillpoint`\n"
        "- **Cấp Điểm**: Cấp điểm kỹ năng cho người dùng (chỉ vai trò JRA).\n"
        "  Cú pháp: `!skillpoint add <@user> <points>`\n"
        "  Ví dụ: `!skillpoint add @FineMotion 50`\n\n"
        "**Dùng `!Finehelp shop` để xem hướng dẫn về shop.**\n"
        "**Nếu có câu hỏi hay thắc mắc gì thì liên hệ JRA hoặc ~~Fine Motion~~ Buena Vista/KyouKoto để được giải đáp.**"
    )
    await ctx.send(help_message_part1)
    await ctx.send(help_message_part2)
    await ctx.send(help_message_part3)

# Calc
@bot.command()
async def calc(ctx, *args):
    if not args:
        await ctx.send("Invalid format. Use one of:\n"
                       "- !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>\n"
                       "- !calc save <CalcType> <name> <X>\n"
                       "- !calc reset [<name>]\n"
                       "- !calc race <name> <distance>\n"
                       "- !calc <CalcType> <name> <X>\n"
                       "- !calc <CalcType> <Spd> <Sta> <Pow> <Gut> <Wit> <X>\n"
                       "Valid CalcTypes: StartFront, StartPace, StartLate, StartEnd, MidFront, MidPace, MidLate, MidEnd, FinalFront, FinalPace, FinalEnd, FinalLate")
        return

    # Import
    if args[0].lower() == 'import':
        input_str = ' '.join(args[1:]).split('|')
        if len(input_str) != 2:
            await ctx.send(
                "Invalid import format. Missing '|' separator. Use: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>")
            return
        stats_part, modifiers_part = [part.strip().split() for part in input_str]

        if len(stats_part) != 6:
            await ctx.send(
                f"Invalid import format. Expected 6 stats before '|' (name, Spd, Sta, Pow, Gut, Wit), got {len(stats_part)}. Use: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>")
            return
        name, spd, sta, pow, gut, wit = stats_part

        if len(modifiers_part) != 3:
            await ctx.send(
                f"Invalid import format. Expected 3 modifiers after '|' (Surface, Distance, Strategy), got {len(modifiers_part)}. Use: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>")
            return
        surface, distance, strategy = modifiers_part

        stats, error = parse_stats(spd, sta, pow, gut, wit, surface, distance, strategy)
        if error:
            await ctx.send(error)
            return
        character_stats[name] = {
            'Spd': stats['Spd'],
            'Sta': stats['Sta'],
            'Pow': stats['Pow'],
            'Gut': stats['Gut'],
            'Wit': stats['Wit'],
            'Surface': stats['Surface'],
            'Distance': stats['Distance'],
            'Strategy': stats['Strategy'],
            'StartScore': 0.0,
            'MidScore': 0.0,
            'FinalScore': 0.0,
            'MidTotalScore': 0.0,
            'FinalTotalScore': 0.0,
            'Bracket': '',
            'Overflow': 0.0
        }
        save_stats()
        await ctx.send(
            f"Stats saved for {name}: Spd={stats['Spd']:.2f} ({stats['Surface']}), Sta={stats['Sta']:.2f}, Pow={stats['Pow']:.2f} ({stats['Distance']}), Gut={stats['Gut']:.2f}, Wit={stats['Wit']:.2f} ({stats['Strategy']})")
        return

    # Calc save
    if args[0].lower() == 'save':
        if len(args) != 4:
            await ctx.send(
                f"Invalid save format. Expected 3 arguments (CalcType, name, X), got {len(args) - 1}. Use: !calc save <CalcType> <name> <X>")
            return
        calc_type, name, x = args[1:4]
        try:
            x = float(x)
        except ValueError:
            await ctx.send("Invalid X value. X must be a number. Use: !calc save <CalcType> <name> <X>")
            return
        if name not in character_stats:
            await ctx.send(
                f"No stats found for {name}. Import stats using: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy> <Style>")
            return
        stats = character_stats[name]
        spd = stats['Spd']
        sta = stats['Sta']
        pow = stats['Pow']

        try:
            # Parse calc_type to phase and style
            calc_type_lower = calc_type.lower()
            if calc_type_lower.startswith('start'):
                phase = 'Start'
                style_str = calc_type_lower[5:].capitalize()
            elif calc_type_lower.startswith('mid'):
                phase = 'Mid'
                style_str = calc_type_lower[3:].capitalize()
            elif calc_type_lower.startswith('final'):
                phase = 'Final'
                style_str = calc_type_lower[5:].capitalize()
            else:
                await ctx.send(
                    "Invalid calc type. Valid types are: StartFront, StartPace, StartLate, StartEnd, MidFront, MidPace, MidLate, MidEnd, FinalFront, FinalPace, FinalEnd, FinalLate")
                return

            if style_str not in ['Front', 'Pace', 'Late', 'End']:
                await ctx.send("Invalid style in calc type. Valid styles are Front, Pace, Late, End.")
                return

            multiplier = multipliers[phase][style_str]

            spd_prime = spd * multiplier
            sta_prime = sta * multiplier
            pow_prime = pow * multiplier

            if phase == 'Start':
                result = x + spd_prime / 10 + sta_prime / 30 + pow_prime / 20
                formula = f"{x} + (Spd' / 10) + (Sta' / 30) + (Pow' / 20)"
            elif phase == 'Mid':
                result = x + spd_prime / 20 + sta_prime / 20 + pow_prime / 20
                formula = f"{x} + (Spd' / 20) + (Sta' / 20) + (Pow' / 20)"
            elif phase == 'Final':
                result = x + spd_prime / 30 + sta_prime / 10 + pow_prime / 20
                formula = f"{x} + (Spd' / 30) + (Sta' / 10) + (Pow' / 20)"

        # Debuff
            debuff_msg = ""
            if phase == 'Start' and random.random() < 0.1:
                result -= 2
                debuff_msg = "\nDebuff: Late Start (-2 points)"
            if random.random() < 0.1:
                result += 3
                stats['Sta'] *= 0.9
                save_stats()
                debuff_msg += "\nDebuff: Rushed (+3 points, -10% stamina)"
            if phase == 'Final' and random.random() < 0.1:
                result -= 5
                debuff_msg += "\nDebuff: Blocked (-5 points)"

            # Overflow cap for Start and Mid phases (non-Front)
            overflow = 0.0
            bracket = stats.get('Bracket', '')
            if bracket and phase in ['Start', 'Mid'] and style_str != 'Front':
                front_max = 0.0
                for char_name, char_stats in character_stats.items():
                    if char_stats.get('Bracket') == bracket and char_stats.get('Strategy', 'C') in ['B', 'A', 'S']:
                        if phase == 'Start':
                            front_max = max(front_max, char_stats.get('StartScore', 0.0))
                        elif phase == 'Mid':
                            front_max = max(front_max, char_stats.get('MidTotalScore', 0.0))

                if style_str == 'Pace':
                    max_allowed = front_max - 5
                elif style_str == 'Late':
                    max_allowed = front_max - 8
                elif style_str == 'End':
                    max_allowed = front_max - 12
                else:
                    max_allowed = float('inf')

                if result > max_allowed:
                    overflow = result - max_allowed
                    stats['Overflow'] = stats.get('Overflow', 0.0) + overflow
                    result = max_allowed

            overflow_bonus = 0.0

            if phase == 'Start':
                stats['StartScore'] = result
                stats['MidTotalScore'] = result
                stats['FinalTotalScore'] = result
            elif phase == 'Mid':
                stats['MidScore'] = result
                stats['MidTotalScore'] = stats['StartScore'] + result
                stats['FinalTotalScore'] = stats['MidTotalScore']
            elif phase == 'Final':
                overflow_bonus = stats.get('Overflow', 0.0) * 0.7
                result += overflow_bonus
                stats['FinalScore'] = result
                stats['FinalTotalScore'] = stats['MidTotalScore'] + result

            save_stats()

            output = f"**{calc_type} Calculation**\n"
            output += f"Formula: {formula}\n"

            original_result = result
            if overflow > 0:
                original_result = result + overflow
                output += f"Result: {result:.2f} (Original: {original_result:.2f})\n"
                output += f"Overflow (capped): {overflow:.2f}\n"
            else:
                output += f"Result: {result:.2f}\n"

            if phase == 'Final' and stats.get('Overflow', 0.0) > 0:
                output += f"Carried overflow bonus (70%): +{overflow_bonus:.2f}\n"

            if phase in ['Mid', 'Final']:
                output += f"Total so far: {stats['FinalTotalScore']:.2f}\n"

            if debuff_msg:
                output += debuff_msg

            await ctx.send(output)

        except Exception as e:  
            await ctx.send(f"Error in save calculation: {str(e)}")
        return

    # Reset
    if args[0].lower() == 'reset':
        if len(args) > 2:
            await ctx.send("Invalid format. Use: !calc reset or !calc reset <name>")
            return
        if ctx.author.name != "SpecificUser":
            await ctx.send("Only 'SpecificUser' can reset stats.")
            return
        if len(args) == 2:
            name = args[1]
            if name not in character_stats:
                await ctx.send(f"No stats found for {name}.")
                return
            if 'Overflow' in character_stats[name]:
                character_stats[name]['Overflow'] = 0.0
            del character_stats[name]
            save_stats()
            await ctx.send(f"Stats and overflow for {name} have been reset.")
            return
        # Reset all
        for name in character_stats:
            character_stats[name]['Overflow'] = 0.0
        character_stats.clear()
        save_stats()
        await ctx.send("All stored stats and overflow values have been reset.")
        return

    # Race
    if args[0].lower() == 'race':
        if len(args) < 2:
            await ctx.send(
                f"Invalid race format. Expected at least 1 argument (name), got {len(args) - 1}. Use: !calc race <name> [<base_stamina>]")
            return
        name = args[1]
        if name not in character_stats:
            await ctx.send(
                f"No stats found for {name}. Import stats using: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>")
            return
        if len(args) == 3:
            base_stamina = float(args[2])
        else:
            base_stamina = skill_data['base_stamina']
            if base_stamina == 0.0:
                await ctx.send(
                    "Base stamina not set. Use !calc race import <base_stamina> to set it or provide it in the command.")
                return
        stats = character_stats[name]
        stamina = stats['Sta']
        guts = stats['Gut']
        dice_roll = random.randint(1, 10)
        x = stamina + guts - base_stamina - dice_roll
        output = f"**Race Check for {name}**\nBase Stamina: {base_stamina}\nStamina: {stamina}\nGuts: {guts}\n1d10 Roll: {dice_roll}\nX = {x:.2f} (Stamina + Guts - Base Stamina - 1d10)\n"

        if x >= 0:
            output += "Result: Character is not fatigued."
        else:
            deficit = -x
            if 5 <= deficit <= 14:
                output += "Result: Fatigued! -1 score in current phase."
            elif 15 <= deficit <= 29:
                output += "Result: Fatigued! -3 score in current phase."
            elif 30 <= deficit <= 50:
                output += "Result: Fatigued! -5 score and cannot activate skills in current phase."
            else:  # deficit > 50
                output += "Result: Fatigued! -10 score and cannot activate skills from this phase to end of race."

        await ctx.send(output)
        return

    if len(args) == 3:  # !calc <CalcType> <Name> <X>
        calc_type, name, x = args
        try:
            x = float(x)
        except ValueError:
            await ctx.send("Invalid X value. X must be a number. Use: !calc <CalcType> <name> <X>")
            return
        if name not in character_stats:
            await ctx.send(
                f"No stats found for {name}. Import stats using: !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>")
            return
        stats = character_stats[name]
    elif len(args) == 7:  # !calc <CalcType> <Spd> <Sta> <Pow> <Gut> <Wit> <X>
        calc_type, spd, sta, pow, gut, wit, x = args
        stats = parse_stats(spd, sta, pow, gut, wit, 'b', 'b', 'b')  # Default B for direct input
        if not stats:
            await ctx.send(
                "Invalid stats format. Spd, Sta, Pow, Gut, Wit must be numbers. Use: !calc <CalcType> <Spd> <Sta> <Pow> <Gut> <Wit> <X>")
            return
        try:
            x = float(x)
        except ValueError:
            await ctx.send(
                "Invalid X value. X must be a number. Use: !calc <CalcType> <Spd> <Sta> <Pow> <Gut> <Wit> <X>")
            return
    else:
        await ctx.send("Invalid format. Use one of:\n"
                       "- !calc import <name> <Spd> <Sta> <Pow> <Gut> <Wit> | <Surface> <Distance> <Strategy>\n"
                       "- !calc save <CalcType> <name> <X>\n"
                       "- !calc reset\n"
                       "- !calc race <name> <distance>\n"
                       "- !calc <CalcType> <name> <X>\n"
                       "- !calc <CalcType> <Spd> <Sta> <Pow> <Gut> <Wit> <X>\n"
                       "Valid CalcTypes: StartFront, StartPace, StartLate, StartEnd, MidFront, MidPace, MidLate, MidEnd, FinalFront, FinalPace, FinalEnd, FinalLate")
        return


    spd = stats['Spd']
    sta = stats['Sta']
    pow = stats['Pow']

    # Parse calc_type to phase and style
    calc_type_lower = calc_type.lower()
    if calc_type_lower.startswith('start'):
        phase = 'Start'
        style_str = calc_type_lower[5:].capitalize()
    elif calc_type_lower.startswith('mid'):
        phase = 'Mid'
        style_str = calc_type_lower[3:].capitalize()
    elif calc_type_lower.startswith('final'):
        phase = 'Final'
        style_str = calc_type_lower[5:].capitalize()
    else:
        await ctx.send(
            "Invalid calc type. Valid types are: StartFront, StartPace, StartLate, StartEnd, MidFront, MidPace, MidLate, MidEnd, FinalFront, FinalPace, FinalEnd, FinalLate")
        return

    if style_str not in ['Front', 'Pace', 'Late', 'End']:
        await ctx.send("Invalid style in calc type. Valid styles are Front, Pace, Late, End.")
        return

    multiplier = multipliers[phase][style_str]

    spd_prime = spd * multiplier
    sta_prime = sta * multiplier
    pow_prime = pow * multiplier

    if phase == 'Start':
        result = x + spd_prime / 10 + sta_prime / 30 + pow_prime / 20
        formula = f"{x} + (Spd' / 10) + (Sta' / 30) + (Pow' / 20)"
    elif phase == 'Mid':
        result = x + spd_prime / 20 + sta_prime / 20 + pow_prime / 20
        formula = f"{x} + (Spd' / 20) + (Sta' / 20) + (Pow' / 20)"
    elif phase == 'Final':
        result = x + spd_prime / 30 + sta_prime / 10 + pow_prime / 20
        formula = f"{x} + (Spd' / 30) + (Sta' / 10) + (Pow' / 20)"

    await ctx.send(f"**{calc_type} Calculation**\nFormula: {formula}\nResult: {result:.2f}")


# !Frace
@bot.command()
async def Frace(ctx, *args):
    if not args:
        await ctx.send("Invalid format. Use one of:\n"
                       "- !Frace import <name1> [<name2> ...] <A/B/C>\n"
                       "- !Frace unique <name> <Spd% or flat> <Sta% or flat> <Pow% or flat> <Gut% or flat> <Wit% or flat> <StartScore>\n"
                       "- !Frace unique all <A/B/C> <Spd% or flat> <Sta% or flat> <Pow% or flat> <Gut% or flat> <Wit% or flat> <StartScore>\n"
                       "- !Frace <A/B/C>")
        return
    if args[0].lower() == 'unique' and not any(role.name == ALLOWED_ROLE for role in ctx.author.roles):
        await ctx.send(f"Only users with the '{ALLOWED_ROLE}' role can apply unique modifiers.")
        return

    if args[0].lower() == 'import':
        if len(args) < 3:
            await ctx.send("Invalid import format. Use: !Frace import <name1> [<name2> ...] <A/B/C>")
            return
        bracket = args[-1].upper()
        if bracket not in ['A', 'B', 'C']:
            await ctx.send("Bracket must be A, B, or C.")
            return
        names = args[1:-1]
        invalid = [n for n in names if n not in character_stats]
        if invalid:
            await ctx.send(f"No stats found for: {', '.join(invalid)}")
            return
        for name in names:
            character_stats[name]['Bracket'] = bracket
        save_stats()
        await ctx.send(f"Registered {', '.join(names)} to bracket {bracket}.")
        return

    # Unique
    if args[0].lower() == 'unique':
        # Single
        if len(args) == 8:
            name = args[1]
            if name not in character_stats:
                await ctx.send(f"No stats found for {name}.")
                return

            try:
                spd_mod, sta_mod, pow_mod, gut_mod, wit_mod, start_score_str = args[2:8]
                start_score = float(start_score_str)

                modifiers = []
                for mod, stat in [(spd_mod, 'Spd'), (sta_mod, 'Sta'), (pow_mod, 'Pow'),
                                  (gut_mod, 'Gut'), (wit_mod, 'Wit')]:
                    if mod.endswith('%'):
                        value = float(mod[:-1]) / 100
                        modifiers.append((stat, value, True))
                    else:
                        value = float(mod)
                        modifiers.append((stat, value, False))

                stats = character_stats[name]
                output = [f"Applied unique modifiers for **{name}**:"]
                for stat, value, is_percent in modifiers:
                    old = stats[stat]
                    if is_percent:
                        stats[stat] *= (1 + value)
                    else:
                        stats[stat] += value
                    diff = stats[stat] - old
                    output.append(f"  {stat}: **{stats[stat]:.2f}** ({diff:+.2f})")

                stats['StartScore'] = stats.get('StartScore', 0) + start_score
                stats['MidTotalScore'] = stats.get('StartScore', 0) + stats.get('MidScore', 0)
                stats['FinalTotalScore'] = stats.get('MidTotalScore', 0) + stats.get('FinalScore', 0)
                output.append(f"  StartScore +{start_score:.2f}")

                save_stats()
                await ctx.send("\n".join(output))
                return

            except Exception as e:
                await ctx.send(f"Error applying unique modifiers:\n{str(e)}")
                return

        # All in bracket
        elif len(args) == 9 and args[1].lower() == 'all':
            bracket = args[2].upper()
            if bracket not in ['A', 'B', 'C']:
                await ctx.send("Bracket must be A, B, or C.")
                return

            bracket_chars = [name for name, stats in character_stats.items() if stats.get('Bracket') == bracket]
            if not bracket_chars:
                await ctx.send(f"No characters in bracket {bracket}.")
                return

            try:
                spd_mod, sta_mod, pow_mod, gut_mod, wit_mod, start_score_str = args[3:9]
                start_score = float(start_score_str)

                modifiers = []
                for mod, stat in [(spd_mod, 'Spd'), (sta_mod, 'Sta'), (pow_mod, 'Pow'),
                                  (gut_mod, 'Gut'), (wit_mod, 'Wit')]:
                    if mod.endswith('%'):
                        value = float(mod[:-1]) / 100
                        modifiers.append((stat, value, True))
                    else:
                        value = float(mod)
                        modifiers.append((stat, value, False))
            except ValueError:
                await ctx.send("Invalid numbers. Use format like 10%, -5, 0, etc.")
                return

            output = [f"Applied unique modifiers to **all** in bracket {bracket}:"]
            for name in bracket_chars:
                stats = character_stats[name]
                char_lines = [f"**{name}**:"]
                for stat, value, is_percent in modifiers:
                    old = stats[stat]
                    if is_percent:
                        stats[stat] *= (1 + value)
                    else:
                        stats[stat] += value
                    diff = stats[stat] - old
                    char_lines.append(f"  {stat}: **{stats[stat]:.2f}** ({diff:+.2f})")
                stats['StartScore'] = stats.get('StartScore', 0) + start_score
                stats['MidTotalScore'] = stats.get('StartScore', 0) + stats.get('MidScore', 0)
                stats['FinalTotalScore'] = stats.get('MidTotalScore', 0) + stats.get('FinalScore', 0)
                char_lines.append(f"  StartScore +{start_score:.2f}")
                output.append("\n".join(char_lines))

            save_stats()
            await ctx.send("\n\n".join(output))
            return

        else:
            await ctx.send("Invalid unique format. Use either:\n"
                           "Single: !Frace unique <name> <Spd> <Sta> <Pow> <Gut> <Wit> <StartScore>\n"
                           "All:    !Frace unique all <A/B/C> <Spd> <Sta> <Pow> <Gut> <Wit> <StartScore>")
            return

    # Bracket display
    if len(args) != 1 or args[0].upper() not in ['A', 'B', 'C']:
        await ctx.send("Invalid format. Use: !Frace <A/B/C> or one of the unique commands above.")
        return

    bracket = args[0].upper()

    bracket_chars = [(name, stats) for name, stats in character_stats.items() if stats.get('Bracket') == bracket]
    if not bracket_chars:
        await ctx.send(f"No characters in bracket {bracket}.")
        return

    # Sort: highest FinalTotalScore → highest Wit
    sorted_chars = sorted(
        bracket_chars,
        key=lambda x: (-x[1].get('FinalTotalScore', 0), -x[1].get('Wit', 0)),
    )

    output = f"**Bracket {bracket} Scores**\n"
    for i, (name, stats) in enumerate(sorted_chars, 1):
        score = stats.get('FinalTotalScore', 0) or stats.get('MidTotalScore', 0) or stats.get('StartScore', 0)

        overflow = stats.get('Overflow', 0.0)
        carried = overflow * 0.7
        overflow_str = f" (Overflow: {overflow:.2f} → carried 70%: +{carried:.2f})" if overflow > 0 else ""

        place = f"{i}{'st' if i == 1 else 'nd' if i == 2 else 'rd' if i == 3 else 'th'}"
        output += f"{place}: {name}: {score:.2f}{overflow_str}\n"

    await ctx.send(output)

# !dueling
@bot.command()
async def dueling(ctx):
    # Get all characters
    all_chars = [(name, stats) for name, stats in character_stats.items() if stats['FinalTotalScore'] > 0]
    if not all_chars:
        await ctx.send("No characters with FinalTotalScore.")
        return
    sorted_chars = sorted(all_chars, key=lambda x: x[1]['FinalTotalScore'], reverse=True)

    # Find groups within 5 points
    groups = []
    current_group = [sorted_chars[0]]
    for i in range(1, len(sorted_chars)):
        if sorted_chars[i - 1][1]['FinalTotalScore'] - sorted_chars[i][1]['FinalTotalScore'] < 5:
            current_group.append(sorted_chars[i])
        else:
            if len(current_group) > 1:
                groups.append(current_group)
            current_group = [sorted_chars[i]]
    if len(current_group) > 1:
        groups.append(current_group)

    if not groups:
        await ctx.send("No groups within 5 points.")
        return

    output = ""
    for group in groups:
        # Sort group by Guts
        sorted_group = sorted(group, key=lambda x: x[1]['Gut'], reverse=True)
        max_guts_name = sorted_group[0][0]
        output += f"Dueling group: {', '.join(n for n, s in group)}\n"
        output += f"Highest Guts: {max_guts_name} (+5 points)\n"
        character_stats[max_guts_name]['FinalTotalScore'] += 5
        for name, stats in sorted_group[1:]:
            output += f"{name} (+2 points)\n"
            character_stats[name]['FinalTotalScore'] += 2

    save_stats()
    await ctx.send(output)


# !Froll
@bot.command()
async def Froll(ctx, y: str):
    try:
        y_int = int(y)
        if y_int < 1:
            await ctx.send("Y must be a positive number.")
            return

        roll = random.randint(1, y_int)
        await ctx.send(f"Rolled: {roll}")

    except ValueError:
        await ctx.send("Invalid input. Y must be a positive number. Use: !Froll <Y>")
    except Exception as e:
        await ctx.send(f"Error in Froll: {str(e)}")

# !Fshop
@bot.command(name='Fshop')
async def Fshop(ctx, *args):
    if not args:
        if not skill_data["shop"]:
            await ctx.send("The shop is empty. Configure it with: !Fshop config \"<SkillName>\" <Cost> <Emoji> [\"<SkillName>\" <Cost> <Emoji> ...]")
            return
        output = "**Skill Shop**\n"
        for skill, data in skill_data["shop"].items():
            emoji = data["emoji"] or ""
            output += f"{skill} {emoji}: {data['cost']:.2f} SP\n"
        await ctx.send(output)
        return

    if args[0].lower() == 'config':
        if not any(role.name == ALLOWED_ROLE for role in ctx.author.roles):
            await ctx.send(f"Only users with the '{ALLOWED_ROLE}' role can configure the shop.")
            return
        if len(args) < 4 or len(args) % 3 != 1:
            await ctx.send("Invalid format. Expected skill name, cost, and emoji triples. Use: !Fshop config \"<SkillName>\" <Cost> <Emoji> [\"<SkillName>\" <Cost> <Emoji> ...]")
            return
        new_shop = {}
        try:
            for i in range(1, len(args), 3):
                skill = args[i].strip('"')
                cost = float(args[i+1])
                emoji = args[i+2]
                if cost <= 0:
                    raise ValueError(f"Cost for {skill} must be positive.")
                new_shop[skill] = {"cost": cost, "emoji": emoji}
        except ValueError as e:
            await ctx.send(f"Error: {str(e)}. Costs must be positive numbers.")
            return
        skill_data["shop"] = new_shop
        save_skill_data()
        await ctx.send(f"Shop configured with {len(new_shop)} skills: {', '.join(f'{k} {v['emoji']}: {v['cost']:.2f} SP' for k, v in new_shop.items())}")
        return

    if args[0].lower() == 'buy':
        if len(args) != 2:
            await ctx.send("Invalid format. Use: !Fshop buy \"<SkillName>\"")
            return
        skill = args[1].strip('"')
        user_id = str(ctx.author.id)
        if skill not in skill_data["shop"]:
            await ctx.send(f"Skill '{skill}' not found in shop. Use: !Fshop to view available skills.")
            return
        cost = skill_data["shop"][skill]["cost"]
        if user_id not in skill_data["user_points"]:
            skill_data["user_points"][user_id] = {"points": 0.0, "skills": []}
        if skill_data["user_points"][user_id]["points"] < cost:
            await ctx.send(f"Insufficient skill points. You have {skill_data['user_points'][user_id]['points']:.2f} pts, need {cost:.2f} pts for {skill}.")
            return
        skill_data["user_points"][user_id]["points"] -= cost
        skill_data["user_points"][user_id]["skills"].append(skill)
        save_skill_data()
        await ctx.send(f"Purchased {skill} for {cost:.2f} pts. You now have {skill_data['user_points'][user_id]['points']:.2f} pts.")
        return

    if args[0].lower() == 'clear':
        if not any(role.name == ALLOWED_ROLE for role in ctx.author.roles):
            await ctx.send(f"Only users with the '{ALLOWED_ROLE}' role can clear the shop.")
            return
        skill_data["shop"] = {}
        save_skill_data()
        await ctx.send("All skills have been removed from the shop.")
        return

    await ctx.send("Invalid format. Use: !Fshop or !Fshop config \"<SkillName>\" <Cost> <Emoji> [\"<SkillName>\" <Cost> <Emoji> ...] or !Fshop buy \"<SkillName>\" or !Fshop clear")

# !skillpoint
@bot.command()
async def skillpoint(ctx, *args):
    user_id = str(ctx.author.id)
    if not args:
        if user_id not in skill_data["user_points"]:
            skill_data["user_points"][user_id] = {"points": 0.0, "skills": []}
        points = skill_data["user_points"][user_id]["points"]
        skills = skill_data["user_points"][user_id]["skills"]
        skills_str = ", ".join(skills) if skills else "None"
        await ctx.send(f"**Your Skill Points**: {points:.2f} pts\n**Purchased Skills**: {skills_str}")
        return

    if args[0].lower() == 'add':
        if not any(role.name == ALLOWED_ROLE for role in ctx.author.roles):
            await ctx.send(f"Only users with the '{ALLOWED_ROLE}' role can give skill points.")
            return
        if len(args) != 3:
            await ctx.send("Invalid format. Use: !skillpoint add <@user> <points>")
            return
        if not ctx.message.mentions:
            await ctx.send("You must mention a user. Use: !skillpoint add <@user> <points>")
            return
        target_id = str(ctx.message.mentions[0].id)
        try:
            points = float(args[2])
            if points <= 0:
                raise ValueError("Points must be positive.")
        except ValueError:
            await ctx.send("Invalid points value. Must be a positive number. Use: !skillpoint add <@user> <points>")
            return
        if target_id not in skill_data["user_points"]:
            skill_data["user_points"][target_id] = {"points": 0.0, "skills": []}
        skill_data["user_points"][target_id]["points"] += points
        save_skill_data()
        await ctx.send(f"Awarded {points:.2f} pts to {ctx.message.mentions[0].name}. They now have {skill_data['user_points'][target_id]['points']:.2f} pts.")
        return

    await ctx.send("Invalid format. Use: !skillpoint or !skillpoint add <@user> <points>")


bot.run(#Token here)
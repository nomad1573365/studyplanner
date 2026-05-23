from src.core import services as sv, repository as rp
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.utils.async_tools import get_lock
from src.core.models import Goal

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands, ui

import datetime
from datetime import date


class GoalsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def goallist_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
        ) -> list[app_commands.Choice[str]]:
            user = await sv.ensure_user(str(interaction.user.id))
            user_id = user.id
            goals = await rp.PgGoalRepository().find_by_user(user_id)
            today = date.today()
            choices = []
            for goal in goals:
                goal_name = goal.goal_name
                if current.lower() in goal_name.lower():
                    choices.append(app_commands.Choice(name=goal_name, value=goal_name))
            return choices[:25]
    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="make_goal",description="ゴール(参考書)の作成")
    async def make_goal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MakegoalModal(self.bot))
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.autocomplete(goal_name=goallist_autocomplete)
    @app_commands.command(name="edit_goal",description="ゴール(参考書)の日付などを編集")
    async def edit_goal(self, interaction: discord.Interaction, goal_name: str):
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        goal = await rp.PgGoalRepository().find_by_name(user_id, goal_name)
        await interaction.response.send_modal(EditgoalModal(self.bot, goal, goal.goal_id))

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="goals",description="ゴール一覧を表示")
    async def goals(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /goals by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        goal_list = await rp.PgGoalRepository().find_by_user(user_id)
        output = discord_ui.show_goals_summary(goal_list)
        await interaction.followup.send(f"{ output }")
        logger.info("/goals succeeded")
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="goals_pub",description="ゴール一覧を表示(/goals)し、それを公開します")
    async def goals_pub(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /goals by {interaction.user.id}")
        await interaction.response.defer()
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        goal_list = await rp.PgGoalRepository().find_by_user(user_id)
        output = discord_ui.show_goals_summary(goal_list)
        await interaction.followup.send(f"{ output }")
        logger.info("/goals_pub succeeded")
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.autocomplete(goal_name=goallist_autocomplete)
    @app_commands.command(name="delete_goal",description="※注意※ゴールの削除です")
    async def delete_goal(self, interaction: discord.Interaction, goal_name: str):
        logger.info(f"COMMAND: /delete_goal {goal_name} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        dmr = rp.PgDashboardMsgRepository()
        dashboard_cog = self.bot.get_cog("DashboardCog")

        lock = get_lock(user_id)
        async with lock:
            msgid_snapshot = await dmr.fetch_user_msgid_list(user_id)
            goal = await rp.PgGoalRepository().find_by_name(user_id, goal_name)
            await rp.PgGoalRepository().delete(goal.goal_id)
            if dashboard_cog and hasattr(dashboard_cog, "_generate_dashboard_unlocked"):
                await dashboard_cog._generate_dashboard_unlocked(
                    user_id,
                    msgid_snapshot=msgid_snapshot,
                )
            else:
                await sv.apply_suggestions_to_daily_plan(user_id)
                self.bot.dispatch("generate_dashboard", user_id)
        await interaction.followup.send(f":white_check_mark:正常に削除されました。")
        logger.info("/delete_goal succeeded")
        
        
        
class MakegoalModal(ui.Modal):
    def __init__(self, bot: commands.bot):
        super().__init__(title="ゴール設定", custom_id="make_goal_modal")
        self.bot = bot
        
    goal_name = ui.TextInput(
        label='ゴールの名前(参考書名など)',
        style=discord.TextStyle.short,
        placeholder='(例) FocusGold数3',
        required=True
    )

    start_point = ui.TextInput(
        label='開始位置(4ページから始めたい場合→4を入力)',
        style=discord.TextStyle.short,
        placeholder='1',
        required=True
    )

    end_point = ui.TextInput(
        label='終了位置(開始位置と同様)',
        style=discord.TextStyle.short,
        placeholder='100',
        required=True
    )

    start_date = ui.TextInput(
        label='開始日(空の場合は今日の日付が入力されます)',
        style=discord.TextStyle.short,
        placeholder='2026-4-20 (日付) または、100 (日後) のように入力',
        required=False,
        max_length=10
    )

    end_date = ui.TextInput(
        label='終了日(開始日と同様)',
        style=discord.TextStyle.short,
        placeholder='2026-4-20(日付) または、100(日後) のように入力',
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        goal_name_value = str(self.goal_name.value)
        start_point_value = int(self.start_point.value)
        end_point_value = int(self.end_point.value)
        start_date_value = str(self.start_date.value)
        end_date_value = str(self.end_date.value)
        logger.info(f"COMMAND: /make_goal {goal_name_value} {start_point_value} {end_point_value} {start_date_value} {end_date_value} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        start_date_value = sv.change_to_date(start_date_value)
        end_date_value = sv.change_to_date(end_date_value)

        await rp.PgGoalRepository().create(Goal(user_id, goal_name_value, start_point_value, end_point_value, start_date_value, end_date_value))
        await sv.apply_suggestions_to_daily_plan(user_id)
        
        self.bot.dispatch("generate_dashboard", user_id)
        await interaction.followup.send(":white_check_mark:ゴールが作成されました！", ephemeral=True)
        logger.info("/make_goal succeeded")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.client.on_app_command_error(interaction, error)
        
        
    
class EditgoalModal(ui.Modal):
    def __init__(self, bot: commands.bot, goal: Goal, goal_id: int):
        super().__init__(title="ゴール編集", custom_id="edit_goal_modal")
        self.bot = bot
        self.present_goal = goal
        self.goal_id = goal_id
        
        self.goal_name = ui.TextInput(
            label='ゴールの名前(参考書名など)',
            style=discord.TextStyle.short,
            placeholder='(例) FocusGold数3',
            default=self.present_goal.goal_name,
            required=True
        )

        self.start_point = ui.TextInput(
            label='開始位置(4ページから始めたい場合→4を入力)',
            style=discord.TextStyle.short,
            placeholder='1',
            default=self.present_goal.start_point,
            required=True
        )

        self.end_point = ui.TextInput(
            label='終了位置(開始位置と同様)',
            style=discord.TextStyle.short,
            placeholder='100',
            default=self.present_goal.end_point,
            required=True
        )

        self.start_date = ui.TextInput(
            label='開始日(空の場合は今日の日付が入力されます)',
            style=discord.TextStyle.short,
            placeholder='2026-4-20 (日付) または、100 (日後) のように入力',
            default=self.present_goal.start_date.strftime("%Y-%m-%d"),
            required=True,
            max_length=10
        )

        self.end_date = ui.TextInput(
            label='終了日(開始日と同様)',
            style=discord.TextStyle.short,
            placeholder='2026-4-20(日付) または、100(日後) のように入力',
            default=self.present_goal.end_date.strftime("%Y-%m-%d"),
            required=True,
            max_length=10
        )
        
        self.add_item(self.goal_name)
        self.add_item(self.start_point)
        self.add_item(self.end_point)
        self.add_item(self.start_date)
        self.add_item(self.end_date)

    async def on_submit(self, interaction: discord.Interaction):
        goal_name_value = str(self.goal_name.value)
        start_point_value = int(self.start_point.value)
        end_point_value = int(self.end_point.value)
        start_date_value = str(self.start_date.value)
        end_date_value = str(self.end_date.value)
        
        logger.info(f"COMMAND: /edit_goal {goal_name_value} {start_point_value} {end_point_value} {start_date_value} {end_date_value} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = await sv.ensure_user(str(interaction.user.id))
        user_id = user.id
        start_date_value = sv.change_to_date(start_date_value)
        end_date_value = sv.change_to_date(end_date_value)

        old_goal = await rp.PgGoalRepository().find_by_id(self.goal_id)
        current_progress = old_goal.current_point if old_goal else 0

        goal = Goal(
            user_id=user_id, 
            goal_name=goal_name_value, 
            start_point=start_point_value, 
            end_point=end_point_value, 
            start_date=start_date_value, 
            end_date=end_date_value, 
            goal_id=self.goal_id,
            current_point=current_progress
        )
        
        await rp.PgGoalRepository().save(goal)
        await sv.apply_suggestions_to_daily_plan(user_id)
        
        self.bot.dispatch("generate_dashboard", user_id)
        await interaction.followup.send(":white_check_mark:ゴールが編集されました！", ephemeral=True)
        logger.info("/edit_goal succeeded")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.client.on_app_command_error(interaction, error)
    
async def setup(bot):
    await bot.add_cog(GoalsCog(bot))

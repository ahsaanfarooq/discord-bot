import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# 1) Put your regenerated token here (keep it secret)
TOKEN = "MTM4MDQyNzExMzg5MDQ1MTU0Ng.Gn9eaQ.B1LkN0QDkR6PTeSx26y1YIh5hrDyXA5bO89LT0"
GUILD_ID = 1380445031181058138  # Replace with your Discord server (guild) ID

# Use default intents (no message content intent needed for slash commands)
intents = discord.Intents.default()

# Create the bot instance
bot = commands.Bot(command_prefix="!", intents=intents)


class Bomb(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="bomb", description="Trigger up to 5 newsletter subscriptions"
    )
    @app_commands.describe(email="Email address to subscribe")
    async def bomb(self, interaction: discord.Interaction, email: str):
        # Acknowledge the command immediately (ephemeral so only user sees it)
        await interaction.response.send_message(
            f"📨 Submitting up to 5 registrations for `{email}`...", ephemeral=True
        )

        # Run 5 parallel submissions via Playwright
        async with async_playwright() as p:
            # During debugging, you can set headless=False to watch the browser:
            browser = await p.chromium.launch(headless=True)
            tasks = [self.submit_newsletter(browser, email, i + 1) for i in range(5)]
            await asyncio.gather(*tasks)
            await browser.close()

        # Follow up once done
        await interaction.followup.send(
            f"✅ Completed up to 5 submissions for `{email}`.", ephemeral=True
        )

    async def submit_newsletter(self, browser, email: str, attempt: int):
        context = await browser.new_context()
        page = await context.new_page()
        try:
            # Navigate to the newsletter page
            await page.goto("https://www.babyone.de/newsletter", timeout=60000)

            # Handle cookie acceptance modal if it appears
            try:
                await page.wait_for_selector(
                    "button[data-testid='uc-accept-all-button']", timeout=5000
                )
                await page.click("button[data-testid='uc-accept-all-button']")
                print(f"[Attempt {attempt}] 🍪 Cookie modal accepted")
            except PlaywrightTimeoutError:
                print(f"[Attempt {attempt}] 🍪 No cookie modal or already accepted")

            # Wait for the email input to appear
            # Using id="form-email" as per the form HTML
            email_input = page.locator("input#form-email")
            # Fallback: if that fails, we can also try name attribute
            exists = await email_input.count()
            if exists == 0:
                # fallback locator
                email_input = page.locator("input[name='email']")
                print(
                    f"[Attempt {attempt}] ⚠️ input#form-email not found, using input[name='email']"
                )

            # Wait until the input is visible
            await email_input.wait_for(state="visible", timeout=10000)
            # Fill in the email field
            await email_input.fill(email)
            print(f"[Attempt {attempt}] ✉️ Filled email: {email}")

            # Check the privacy checkbox
            # The HTML: <input name="privacy" type="checkbox" id="form-privacy-opt-in-...">
            privacy_input = page.locator("input[name='privacy']")
            await privacy_input.wait_for(state="attached", timeout=5000)
            # Scroll into view if needed, then check
            try:
                await privacy_input.scroll_into_view_if_needed()
            except Exception:
                pass
            await privacy_input.check()
            print(f"[Attempt {attempt}] 🔒 Privacy checkbox checked")

            # Scope to the ancestor form of the email input
            form = email_input.locator("xpath=ancestor::form")
            # Confirm we found exactly one form
            form_count = await form.count()
            if form_count == 0:
                print(f"[Attempt {attempt}] ❌ No ancestor form found for email input!")
            else:
                # If more than one, Playwright will use the first; we log a warning
                if form_count > 1:
                    print(
                        f"[Attempt {attempt}] ⚠️ Found {form_count} ancestor forms; using the first"
                    )

                # Locate the submit button within that form: <button type="submit" class="btn btn-black">Jetzt anmelden</button>
                # Use get_by_role with exact visible text
                submit_btn = form.get_by_role("button", name="Jetzt anmelden")
                count_btn = await submit_btn.count()
                if count_btn == 0:
                    # fallback: locate by class + type + text via locator
                    submit_btn = form.locator(
                        "button[type='submit'].btn.btn-black", has_text="Jetzt anmelden"
                    )
                    count_btn2 = await submit_btn.count()
                    if count_btn2 == 0:
                        print(
                            f"[Attempt {attempt}] ❌ No submit button 'Jetzt anmelden' found in form!"
                        )
                    else:
                        print(
                            f"[Attempt {attempt}] ⚠️ Found {count_btn2} fallback submit buttons with class btn-black"
                        )
                else:
                    print(
                        f"[Attempt {attempt}] ✅ Found submit button by role: count={count_btn}"
                    )

                # Wait until the button is visible & enabled, then click
                try:
                    await submit_btn.scroll_into_view_if_needed()
                except Exception:
                    pass
                await submit_btn.wait_for(state="visible", timeout=5000)
                await submit_btn.click()
                print(f"[Attempt {attempt}] 🚀 Clicked 'Jetzt anmelden' for {email}")

                # Optionally wait for a success indicator: e.g., look for some thank-you text in German.
                # Inspect the page after successful subscription to determine the selector/text to wait for.
                # For example, if a confirmation message contains "Vielen Dank" or similar:
                try:
                    # This is an example; adjust text according to actual site behavior.
                    await page.wait_for_selector("text=Vielen Dank", timeout=10000)
                    print(
                        f"[Attempt {attempt}] 🎉 Submission confirmed (found 'Vielen Dank')"
                    )
                except PlaywrightTimeoutError:
                    # Maybe the site shows a different confirmation or just reloads; log a warning.
                    print(
                        f"[Attempt {attempt}] ⚠️ No explicit 'Vielen Dank' confirmation found; submission may still have succeeded."
                    )

        except Exception as e:
            print(f"[Attempt {attempt}] ❌ Error on {email}: {e}")
        finally:
            await context.close()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # Debug: show loaded cogs
    print("Loaded Cogs:", list(bot.cogs.keys()))

    # Sync slash commands to the given guild for immediate availability
    try:
        guild = discord.Object(id=GUILD_ID)
        synced_cmds = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced_cmds)} slash command(s) to guild {GUILD_ID}.")
        if synced_cmds:
            print("Commands in this guild after sync:")
            for cmd in synced_cmds:
                print("  -", cmd.name)
        else:
            print(
                "No commands were synced. Check that the Cog is added and the decorator is correct."
            )
        # List all commands in tree for further debugging
        all_cmds = bot.tree.get_commands()
        print("All commands in tree (global prototypes + guild-specific prototypes):")
        for c in all_cmds:
            print("  -", c.name, "(parent:", c.parent, ")")
    except Exception as e:
        print(f"Slash command sync error: {e}")


async def main():
    # Create and add the Cog instance
    bomb_cog = Bomb(bot)
    await bot.add_cog(bomb_cog)

    # Explicitly add the slash command to the tree for the specific guild (if you used this pattern)
    try:
        bot.tree.add_command(bomb_cog.bomb, guild=discord.Object(id=GUILD_ID))
        print("Added slash command 'bomb' to tree for guild", GUILD_ID)
    except Exception as e:
        print("Error adding slash command to tree:", e)

    # Start the bot
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())

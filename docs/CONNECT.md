# Connecting your AIs, and what they cost

Sage OS talks to several kinds of AI. Every AI you connect reads the same library and appears in the same chat
history, and any of them can pick up a chat another one started. In the app, **CONNECT** (from the first-run screen,
or *Install or connect another…* in the AI picker above a chat) has these same steps, with a button to finish each.

| AI | What you need | What it costs |
|---|---|---|
| [A model on this computer](#a-model-on-this-computer) | Nothing; a 3 to 7 GB download | Free; private; works offline |
| [Claude Code](#claude-code) | A Claude Pro or Max plan | Included in your plan, within its limits |
| [ChatGPT (OpenAI)](#chatgpt-openai) | An OpenAI API key | Paid per use (tokens) |
| [Gemini (Google)](#gemini-google) | A Google AI Studio key | Free tier, then paid per use |
| [Ollama](#ollama) | Ollama running on this computer | Free; on this computer |
| [Hermes](#hermes-advanced) | Hermes installed (advanced) | Depends on its models |

## A model on this computer

1. Open **MODELS**. Sage OS looks at this computer and marks each model *runs well here*, *runs, but slowly* or
   *too big*.
2. Pick one that *runs well here* (the biggest of those is usually best) and press **install**. Sage OS fetches llama.cpp,
   the program that runs it, by itself.
3. Press **start**, then pick it in the AI picker above a chat.

Nothing you ask leaves the computer. While a game uses the graphics card, game mode pauses the model and offers a
small one instead.

## Claude Code

1. Install Claude Code from [claude.com/code](https://claude.com/code) (the Claude desktop app includes it).
2. Sign it in once: open a terminal (Mac: Command-Space, type *Terminal*, Return; Windows: the Windows key, type
   *Terminal*, Enter), run `claude auth login`, and finish in the browser.
3. In **CONNECT → Claude Code**, press **CONNECT**. New Claude chats ask which folder Claude may work in. Claude asks
   before running commands or changing files, and those requests appear in your inbox.

Claude Code runs on your plan, not per message, so it has no bill in Sage OS. Your plan has a 5-hour limit and a
weekly limit. Both appear in the top bar and under **USAGE & COSTS** after your first Claude reply. USAGE also shows
what the same work would have cost on the pay-per-use API.

## ChatGPT (OpenAI)

1. Sign in at [platform.openai.com](https://platform.openai.com). A ChatGPT Plus subscription doesn't cover the API;
   it's billed separately.
2. Under **Settings → Billing**, add a payment method or some credit.
3. Open **[API keys](https://platform.openai.com/api-keys)**, create a new secret key and copy it. It's shown only once.
4. In **CONNECT → ChatGPT (OpenAI)**, paste the key and press **CONNECT**.

Sage OS tests the key before keeping it. If OpenAI doesn't accept it, nothing is saved.

## Gemini (Google)

1. Sign in at [aistudio.google.com](https://aistudio.google.com) with a Google account.
2. Press **Get API key → Create API key** and copy the key.
3. In **CONNECT → Gemini (Google)**, paste the key and press **CONNECT**.

The free tier has daily limits. Google may use free-tier prompts to improve its products; paid use isn't.

## Ollama

1. Install Ollama from [ollama.com](https://ollama.com) and pull a model, for example `ollama pull llama3.2`.
2. Leave it running. Sage OS finds it when it starts, or press **LOOK AGAIN** in CONNECT → Ollama.

## Hermes (advanced)

Hermes is a separate agent framework. You don't need it. If you run it, add its profile to this computer's
`config.local.toml`, then restart Sage OS:

```toml
[agents]
hermes = ["default"]
```

## Where your keys are kept

A pasted key goes to your operating system's keychain: **Windows Credential Manager** on Windows and the **macOS
Keychain** on a Mac, under the name *Sage OS*. It is never written to a file and never sent to the page again. Only
Sage OS's own hub reads it, to talk to that provider. **DISCONNECT** removes it from the keychain.

Developers can still set keys in `config.local.toml` with `[[models]]` and `api_key_env`. A provider set there
wins over a keychain key with the same name.

## Usage, limits and costs

**$ USAGE** in the top bar (or the token count in a chat's header) opens **USAGE & COSTS**:

- **Spend:** today, the last 7 days and the last 30 days on API keys. Models on this computer and your Claude plan
  add nothing to it.
- **Claude plan:** what your Claude work would have cost on the pay-per-use API, so you can see what the plan saves.
- **Tokens per day** for the last 30 days, across all AIs.
- **Limits:**
  - Claude reports its 5-hour and weekly use with each reply.
  - OpenAI reports its per-minute token and request limits with each reply.
  - Google doesn't report Gemini's limits; see your quota in AI Studio.
- **By AI:** tokens in and out, and the cost, for each AI and model.
- **Price list:** dollars per million tokens, in and out, for each model. The prices come from each provider's own
  price page and are dated; announced price changes apply from their date.

How a reply is counted:

- Tokens come from the provider's own count. A provider that doesn't report them (some local servers) gets an
  estimate from the text, about four characters a token, marked **≈**.
- Cost is tokens × the price on that day. Claude Code reports its own cost, which knows its cache discounts, so
  Sage OS uses that.
- A model with no listed price shows **no price**. Add one in the price list and new replies are priced with it.

**Prices change.** If a price is out of date, press **EDIT** next to it (or **+ ADD A PRICE** for a model that isn't
listed) and enter what your provider charges. Your price is used from then on, and it follows you to your other
devices. **RESET** goes back to the listed price. Earlier replies keep the cost they had when they were made.

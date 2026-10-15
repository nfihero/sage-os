# Mac first run: the tester's check (F1)

F1's gate is a person on a Mac with nothing installed going from the `.dmg` to a first answer, and sending a problem
report. Every release's build machines already run the packaged app's **self-check** on a fresh macOS and Windows
(`sage-os-hub --self-check OUT --with-engine`): it starts on an empty data folder, checks that nothing is connected
and there are no chats, that the screen, model catalog and price list are bundled, that the OS keychain works, that a
problem report can be made, and that llama.cpp downloads for that machine and runs. A failure stops the release.
This checklist covers what a machine can't: a real person, a real first open, a real email.

Use a Mac that has never had Sage OS on it, or a new macOS user account (System Settings → Users & Groups).

1. **Install.** Download `Sage OS_<version>_aarch64.dmg` from the
   [latest release](https://github.com/nfihero/sage-os/releases/latest), open it, drag Sage OS to Applications.
2. **First open.** Open it from Applications. If macOS says it can't check the app, open System Settings → Privacy &
   Security → **Open Anyway**. Note whether the README's steps were enough.
3. **Empty start.** The first screen offers a model that fits this Mac and other AIs to connect. Nothing should
   already be connected, and there should be no chats.
4. **A model on this Mac.** Press **INSTALL AND START** on the recommended model. Note how long the download and
   start take. A first chat opens: ask it something and get an answer.
5. **Your notes.** Add a note and a document (Library), then ask the chat about them. The reading strip should show
   them.
6. **An AI with a key** (optional). CONNECT → Gemini: follow the steps, paste a key; macOS may ask to let Sage OS use
   the keychain (choose *Always Allow*). Pick Gemini in the AI picker and ask something. $ USAGE shows its tokens.
7. **Report a problem.** Top bar → **REPORT A PROBLEM**: write a sentence, read the report (no notes or chat text in
   it), **SAVE IT AND OPEN AN EMAIL**. Mail opens to roundederror@gmail.com; attach the file from Downloads and send.
   Check it arrives.
8. **Update.** When the next release is out, the amber **UPDATE** chip appears; update and check the note, document
   and chats are still there.

Write down anything confusing, not only what breaks: D41 assumes the tester has never used an AI agent.

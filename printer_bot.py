#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import yaml
import logging
import requests
import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

AFFIRMATIONS = [
    "WRRR-wrrr",
    "WRRRRRRRRRRR",
    "WRRR-wr-WRRR",
    "WRRRR *beep*",
    "wrr-WRR-wrr-WRR-wrr",
    "wrrr-WRRR",
    "wrrr-WRRR-wrrr-WRRR",
    "wrp-wrp-wrp-wrp-wrp-WRRR",
    "WRRRRrrrrRRRRrrrrRRRR",
]

COMMAND_UPDATE_STATUS = "us"
COMMAND_ABORT_PRINT_CONFIRM = "ay"
COMMAND_ABORT_PRINT_CANCEL = "an"

TMP_PIC_PATH = "/tmp/pic"


class PrinterBot:

    def __init__(self):
        self.config = {}

    @staticmethod
    def get_affirmation():
        return random.choice(AFFIRMATIONS)

    def get_headers(self):
        return {"X-Api-Key": self.config['octoprint']['api_key']}

    def post_headers(self):
        headers = self.get_headers()
        headers["Content-Type"] = "application/json"
        return headers

    def get_request(self, path):
        resp = requests.get(self.config['octoprint']['url'] + "/api/" + path, headers=self.get_headers())
        return resp.json()

    def post_request(self, path, body):
        resp = requests.post(self.config['octoprint']['url'] + "/api/" + path, headers=self.post_headers(), json=body)
        logger.info('Posted. ' + str(resp.status_code))
        logger.info(resp.text)


    def has_webcam(self):
        return 'webcam' in self.config

    def has_permission(self, user_id):
        if "approved_users" in self.config:
            if user_id in self.config['approved_users']:
                return True
            else:
                logger.warning('User ID {} has no permissions'.format(user_id))
                return False
        return True

    def has_watch_permission(self, user_id):
        if "approved_watchers" in self.config:
            if user_id in self.config['approved_watchers']:
                return True
        return self.has_permission(user_id)

    @staticmethod
    def get_single_button(text, callback_data):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(text, callback_data=callback_data)
        ]])

    def get_status_message(self):
        status = self.get_request("job")
        state = status['state']
        if "printing" in state.lower():
            print_file = status['job']['file']['display']
            progress = status['progress']['completion']
            time_left = status['progress']['printTimeLeft']

            formatted_time = None
            if time_left:
                formatted_time = str(datetime.timedelta(seconds=time_left))

            msg = "{}\n\n<b>{}</b>\n{}\n{:.2f}% complete\n{} remaining".format(
                self.get_affirmation(),
                state.strip(),
                print_file,
                progress,
                formatted_time or "??:??"
            )
            return msg
        else:
            msg = "<b>{}</b>\n{}".format(
                state,
                self.get_affirmation()
            )
            return msg

    def get_cam_snapshot(self):
        if not self.has_webcam():
            return
        url = self.config['webcam']['url']
        resp = requests.get(url)
        with open(TMP_PIC_PATH, 'wb') as file:
            file.write(resp.content)

    def send_confirmation_message(self, bot, message, text, confirm_cmd, cancel_cmd):
        buttons = [
            [InlineKeyboardButton("Do it!", callback_data=confirm_cmd)],
            [InlineKeyboardButton("No wait!", callback_data=cancel_cmd)],
        ]
        message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # Conversation handlers:
    def handle_status(self, bot, update):
        if not self.has_watch_permission(update.message.from_user.id):
            update.message.reply_text(self.get_affirmation())
            return
        if self.has_webcam():
            self.get_cam_snapshot()
            bot.send_photo(chat_id=update.message.chat.id,
                           photo=open(TMP_PIC_PATH, 'rb'),
                           caption=self.get_status_message(),
                           parse_mode="html",
                           reply_markup=self.get_single_button("Update", COMMAND_UPDATE_STATUS))
        else:
            update.message.reply_text(self.get_status_message(),
                                      parse_mode="html",
                                      reply_markup=self.get_single_button("Update", COMMAND_UPDATE_STATUS))

    def handle_abort(self, bot, update):
        if not self.has_permission(update.message.from_user.id):
            update.message.reply_text(self.get_affirmation())
            return
        status = self.get_request("job")
        state = status['state']
        if "printing" in state.lower():
            self.send_confirmation_message(bot, update.message, "Really abort current print job?", COMMAND_ABORT_PRINT_CONFIRM, COMMAND_ABORT_PRINT_CANCEL)
        else:
            update.message.reply_text("No print job ongoing...")


    def handle_message(self, bot, update):
        if update.message.chat.type != "private":
            return
        if not self.has_watch_permission(update.message.from_user.id):
            update.message.reply_text(self.get_affirmation())
            return
        update.message.reply_text(self.get_affirmation())
    
    def handle_inline_button(self, bot, update):
        query = update.callback_query
        data = update.callback_query.data
        data = data.split(':')

        cmd = data[0]
        message_id = query.message.message_id
        chat_id = query.message.chat.id

        if cmd == COMMAND_UPDATE_STATUS:
            if not self.has_watch_permission(query.from_user.id):
                return
            status = self.get_status_message()

            if self.has_webcam():
                self.get_cam_snapshot()
                bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=InputMediaPhoto(
                        open(TMP_PIC_PATH, 'rb'),
                        caption=status,
                        parse_mode="html"
                    ),
                    reply_markup=self.get_single_button("Update", COMMAND_UPDATE_STATUS)
                )
            else:
                bot.edit_message_text(text=status,
                                      message_id=message_id,
                                      chat_id=chat_id,
                                      parse_mode="html",
                                      reply_markup=self.get_single_button("Update", COMMAND_UPDATE_STATUS))

        if cmd == COMMAND_ABORT_PRINT_CANCEL:
            if not self.has_permission(query.from_user.id):
                return
            bot.edit_message_text(text="Okay, not aborting anything!",
                                  message_id=message_id,
                                  chat_id=chat_id)

        if cmd == COMMAND_ABORT_PRINT_CONFIRM:
            if not self.has_permission(query.from_user.id):
                return
            self.post_request("job", {"command":"cancel"})
            status = self.get_status_message()
            bot.edit_message_text(text="Abort command sent.\n{}".format(status),
                                  message_id=message_id,
                                  chat_id=chat_id,
                                  parse_mode="html")
        query.answer(self.get_affirmation())

    # Help command handler
    def handle_help(self, bot, update):
        """Send a message when the command /help is issued."""
        helptext = "WRRR-wrrr-WRRR-wrrr-wrp-wrp-wrp-WRRR-wrrr-WRRR"

        update.message.reply_text(helptext, parse_mode="Markdown")

    # Error handler
    def handle_error(self, bot, update, error):
        """Log Errors caused by Updates."""
        logger.warning('Update "%s" caused error "%s"', update, error)

    def run(self, opts):
        with open(opts.config, 'r') as configfile:
            config = yaml.load(configfile)
            self.config = config

        """Start the bot."""
        # Create the EventHandler and pass it your bot's token.
        updater = Updater(config['token'])

        # Get the dispatcher to register handlers
        dp = updater.dispatcher

        dp.add_handler(CommandHandler("status", self.handle_status))
        dp.add_handler(CommandHandler("abort", self.handle_abort))
        dp.add_handler(CommandHandler("help", self.handle_help))
        dp.add_handler(CommandHandler("start", self.handle_status))
        dp.add_handler(CallbackQueryHandler(self.handle_inline_button))

        dp.add_error_handler(self.handle_error)

        dp.add_handler(MessageHandler(None, self.handle_message))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()


def main(opts):
    PrinterBot().run(opts)


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config', default='config.yml', type='string',
                      help="Path of configuration file")
    (opts, args) = parser.parse_args()
    main(opts)

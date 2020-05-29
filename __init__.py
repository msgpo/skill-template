from mycroft.messagebus.message import Message, dig_for_message
from mycroft.skills.core import FallbackSkill, intent_file_handler, \
    intent_handler
from adapt.intent import IntentBuilder
import time


def camel_case_split(identifier):
    """Split camel case string"""
    regex = '.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)'
    matches = re.finditer(regex, identifier)
    return ' '.join([m.group(0) for m in matches])


class MySkill(FallbackSkill):
    def __init__(self):
        super(MySkill, self).__init__(name='MySkill')
        # skill settings defaults
        if "intercept_allowed" not in self.settings:
            self.settings["intercept_allowed"] = False
        if "priority" not in self.settings:
            self.settings["priority"] = 50
        if "timeout" not in self.settings:
            self.settings["timeout"] = 15

        # state trackers
        self._converse_keepalive = None
        self.waiting = False
        self.success = False
        self._old_settings = dict(self.settings)

        # events
        self.settings_change_callback = self._on_web_settings_change
        self.namespace = self.__class__.__name__.lower()
        self.skill_name = camel_case_split(self.__class__.__name__)

    def initialize(self):

        self.register_fallback(self.handle_fallback,
                               int(self.settings["priority"]))

        self.add_event(self.namespace + ".success", self.handle_success)
        self.add_event(self.namespace + ".failure", self.handle_failure)
        self.add_event(self.namespace + ".converse.activate",
                       self.handle_converse_enable)
        self.add_event(self.namespace + ".converse.deactivate",
                       self.handle_converse_disable)

        self._converse_keepalive = create_daemon(self.converse_keepalive)

        self.initial_setup()

    def _on_web_settings_change(self):
        for k in self.settings:
            if self.settings[k] != self._old_settings[k]:
                self.handle_new_setting(k, self.settings[k],
                                        self._old_settings[k])
        self._old_settings = dict(self.settings)

    def initial_setup(self):
        pass

    def get_intro_message(self):
        # welcome dialog on skill install
        self.speak_dialog("intro",
                          {"skill_name": self.skill_name})

    # intents
    def handle_utterance(self, utterance):
        # handle both fallback and converse stage utterances
        return False

    @intent_file_handler("converse.enable.intent")
    def handle_converse_enable(self, message):
        if self.settings["intercept_allowed"]:
            self.speak_dialog("converse_on",
                          {"skill_name": self.skill_name})
        else:
            self.speak_dialog("converse_enable",
                          {"skill_name": self.skill_name})
        self.settings["intercept_allowed"] = True

    @intent_file_handler("converse.disable.intent")
    def handle_converse_disable(self, message):
        if not self.settings["intercept_allowed"]:
            self.speak_dialog("converse_off",
                          {"skill_name": self.skill_name})
        else:
            self.speak_dialog("converse_disable",
                          {"skill_name": self.skill_name})
        self.settings["intercept_allowed"] = False

    @intent_handler(IntentBuilder("WhyIntent")
                         .require("WhyKeyword").require("CHANGED"))
    def handle_explain_why(self, message):
        # set context elsewhere to enable this
        self.speak_dialog("why", wait=True)

    # event handlers
    def handle_new_setting(self, key, value, old_value):
        pass

    def handle_success(self, message):
        self.waiting = False
        self.success = True

    def handle_failure(self, message):
        self.waiting = False
        self.success = False

    def wait_for_something(self):
        start = time.time()
        self.success = False
        self.waiting = True
        while self.waiting and \
                time.time() - start < float(self.settings["timeout"]):
            time.sleep(0.1)
        if self.waiting:
            message = dig_for_message()
            if not message:
                message = Message(self.namespace + ".timeout")
            else:
                message.reply(self.namespace + ".timeout")
            self.bus.emit(message)
            self.waiting = False
        return self.success

    # converse
    def converse_keepalive(self):
        while True:
            if self.settings["intercept_allowed"]:
                # avoid converse timed_out
                self.make_active()
            time.sleep(60)

    def converse(self, utterances, lang="en-us"):
        if self.settings["intercept_allowed"]:
            return self.handle_utterance(utterances[0])
        return False

    # fallback
    def handle_fallback(self, message):
        utterance = message.data["utterance"]
        return self.handle_utterance(utterance)

    # shutdown
    def stop_converse(self):
        if self._converse_keepalive is not None and self._converse_keepalive.running:
            self._converse_keepalive.join(2)

    def shutdown(self):
        self.stop_converse()
        super(MySkill, self).shutdown()


def create_skill():
    return MySkill()

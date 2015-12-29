import re
import time

from mumo_module import MumoModule, commaSeperatedIntegers


class AuthSticky(MumoModule):
    default_config = {
        "AuthSticky": (('servers', commaSeperatedIntegers, []), ),
        lambda x: re.match('(all)|(server_\d+)', x): (
            ('not_authed_group', str, 'not_authed'),
            ('not_authed_channel', int, 0),
            ('auth_watchdog', int, 300)
        )
    }

    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()

        self.action_auth = manager.getUniqueAction()

        self.auth_timers = {}

    def connected(self):
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")

        servers = self.cfg().AuthSticky.servers
        if not servers:
            servers = manager.SERVERS_ALL

        manager.subscribeServerCallbacks(self, servers)

    def disconnected(self): pass

    def __on_auth(self, server, action, user, target):
        try:
            server_config = getattr(self.cfg(), 'server_%d' % server.id())
        except AttributeError:
            server_config = self.cfg().all

        assert action == self.action_auth

        if target.userid < 1:
            server.sendMessage(user.session, "You must right-click > register yourself first.")
            return
        if target.session != user.session:
            server.sendMessage(user.session, "You cannot auth other users.")
            return
        # Add if for already authed

        # Check site auth
        server.sendMessage(user.session, "Checking auth for {0}".format(target.userid))
        server.removeUserFromGroup(0, target.session, server_config.not_authed_group)
        server.setState(target)

    def userTextMessage(self, server, user, message, current=None): pass

    def userConnected(self, server, user, context=None):
        try:
            server_cfg = getattr(self.cfg(), 'server_%d' % server.id())
        except AttributeError:
            server_cfg = self.cfg().all

        manager = self.manager()
        has_authed = False

        if user.userid >= 1:
            self.auth_timers[user.userid] = int(time.time())
        server.sendMessage(user.session, "{0} has connected at: {1}".format(
                user.userid, self.auth_timers.get(user.userid, -1)))
        if not has_authed:
            manager.addContextMenuEntry(
                server,
                user,
                self.action_auth,
                "Auth with Dashboard",
                self.__on_auth,
                self.murmur.ContextUser
            )
            server.addUserToGroup(0, user.session, server_cfg.not_authed_group)
            user.channel = server_cfg.not_authed_channel
            server.setState(user)

    def userDisconnected(self, server, user, context=None):
        if user.userid in self.auth_timers:
            del self.auth_timers[user.userid]

    def userStateChanged(self, server, user, context=None):
        try:
            server_cfg = getattr(self.cfg(), 'server_%d' % server.id())
        except AttributeError:
            server_cfg = self.cfg().all

        if user.userid in self.auth_timers and self.auth_timers[user.userid] + server_cfg.auth_watchdog <= time.time():
            self.auth_timers[user.userid] = int(time.time())
            server.sendMessage(user.session, "Renew auth check for {0}".format(user.userid))

            has_authed = False

            if not has_authed:
                server.addUserToGroup(0, user.session, server_cfg.not_authed_group)
                user.channel = server_cfg.not_authed_channel
                server.setState(user)

    def channelCreated(self, server, state, context=None): pass

    def channelRemoved(self, server, state, context=None): pass

    def channelStateChanged(self, server, state, context=None): pass

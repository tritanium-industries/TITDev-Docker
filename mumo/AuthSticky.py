import re
import time

from mumo_module import MumoModule, commaSeperatedIntegers


# noinspection PyPep8Naming
class AuthSticky(MumoModule):
    default_config = {
        "AuthSticky": (('servers', commaSeperatedIntegers, []), ),
        lambda x: re.match('(all)|(server_\d+)', x): (
            ('not_authed_channel', int, 0),
            ('auth_watchdog', int, 300)
        )
    }

    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()

        self.action_auth = manager.getUniqueAction()
        self.action_unauth = manager.getUniqueAction()

        self.auth_timers = {}
        self.auth_cache = set()

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

        assert action == self.action_auth

        if target.userid < 1:
            server.sendMessage(user.session, "You must right-click > register yourself first.")
            return
        if target.session != user.session:
            server.sendMessage(user.session, "You cannot auth other users.")
            return
        if target.userid in self.auth_cache:
            server.sendMessage(user.session, "Already Authed")
            return

        site_authed = True  # Check Site Auth
        self.auth_timers[target.userid] = int(time.time())
        if site_authed:
            server.sendMessage(user.session, "Checking auth for {0}".format(target.userid))
            self.auth_cache.add(target.userid)

    def __on_unauth(self, server, action, user, target):

        assert action == self.action_unauth

        if target.session != user.session:
            server.sendMessage(user.session, "You cannot unauth other users.")
            return
        if target.userid not in self.auth_cache:
            server.sendMessage(user.session, "Already Unauthed")
            return

        server.sendMessage(user.session, "Removed auth for {0}".format(target.userid))
        self.auth_timers[target.userid] = int(time.time())
        self.auth_cache.remove(target.userid)

    def userTextMessage(self, server, user, message, current=None): pass

    # noinspection PyUnusedLocal
    def userConnected(self, server, user, context=None):
        try:
            server_cfg = getattr(self.cfg(), 'server_%d' % server.id())
        except AttributeError:
            server_cfg = self.cfg().all

        manager = self.manager()

        if user.userid >= 1:
            self.auth_timers[user.userid] = int(time.time())
        server.sendMessage(user.session, "{0} has connected at: {1}".format(
                user.userid, self.auth_timers.get(user.userid, -1)))
        manager.addContextMenuEntry(
            server,
            user,
            self.action_auth,
            "Auth with Dashboard",
            self.__on_auth,
            self.murmur.ContextUser
        )
        manager.addContextMenuEntry(
            server,
            user,
            self.action_unauth,
            "Unauth with Dashboard",
            self.__on_unauth,
            self.murmur.ContextUser
        )

        site_auth = False  # Check Site auth
        if not site_auth:
            self.auth_cache.remove(user.userid)
            user.channel = server_cfg.not_authed_channel
            server.setState(user)

    # noinspection PyUnusedLocal
    def userDisconnected(self, server, user, context=None):
        if user.userid in self.auth_timers:
            del self.auth_timers[user.userid]

    # noinspection PyUnusedLocal
    def userStateChanged(self, server, user, context=None):
        try:
            svr_cfg = getattr(self.cfg(), 'server_%d' % server.id())
        except AttributeError:
            svr_cfg = self.cfg().all

        # Do auth checks
        if user.userid < 1:
            # Lock out if user is not authenticated
            site_auth = False
        elif user.userid not in self.auth_timers or (user.userid in self.auth_timers and
                                                     self.auth_timers[user.userid] +
                                                     svr_cfg.auth_watchdog <= time.time()):
            # If cache has expired
            self.auth_timers[user.userid] = int(time.time())
            server.sendMessage(user.session, "Renew auth check for {0}".format(user.userid))
            site_auth = False  # Check for site auth
            self.auth_cache.remove(user.userid)
        elif user.userid in self.auth_cache:
            # If previously site authed and cache hasn't expired
            server.sendMessage(user.session, "Has previously site authed, but cache hasn't expired")
            site_auth = True
        else:
            # If wasn't previously site authed and cache hasn't expired
            server.sendMessage(user.session, "Has not previously been authed and cache hasn't expired")
            site_auth = False

        if not site_auth and user.channel != svr_cfg.not_authed_channel:
            user.channel = svr_cfg.not_authed_channel
            server.setState(user)

    def channelCreated(self, server, state, context=None): pass

    def channelRemoved(self, server, state, context=None): pass

    def channelStateChanged(self, server, state, context=None): pass

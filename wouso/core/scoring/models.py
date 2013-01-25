import logging
from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
from wouso.core.common import Item
from wouso.core.game import get_games
from wouso.core.game.models import Game


class Coin(Item, models.Model):
    """ Different scoring categories.

    A special coin is 'points' since is used for ladder and levels.
    """
    name = models.CharField(max_length=100, unique=True)
    # The coin owner module, or null if is a core coin
    owner = models.ForeignKey(Game, blank=True, null=True)
    title = models.CharField(max_length=100)
    # If the coin values are forced integers, else using float.
    integer = models.BooleanField(default=False, blank=True)

    def is_core(self):
        """ A coin is a core coin, if it doesn't have an owner """
        return self.owner is None

    def format_value(self, amount):
        if self.integer:
            return int(round(amount))
        return amount

class Formula(Item, models.Model):
    """ Define the way coin amounts are given to the user, based
    on keyword arguments formulas.

    A formula is owned by a game, or by the system (set owner to None)
    """
    name = models.CharField(max_length=100, unique=True)
    definition = models.CharField(max_length=1000, default='')
    owner = models.ForeignKey(Game, null=True, blank=True)
    description = models.CharField(max_length=500, default='')

    @classmethod
    def get(cls, id_string, default_string=None):
        """ Performs a get lookup on the Formula table, if no formula exists
        with the first id_string, returns the formula with the default_string
        id.
        """
        if not default_string:
            return super(Formula, cls).get(id_string)

        try:
            formula = Formula.objects.get(name=id_string)
        except cls.DoesNotExist:
            formula = super(Formula, cls).get(default_string)
            return formula
        return formula

class History(models.Model):
    """ Scoring history keeps track of scoring events per user, saving
    the details from source to amount.
    """
    timestamp = models.DateTimeField(default=datetime.now, blank=True)
    user = models.ForeignKey(User)
    game = models.ForeignKey(Game, blank=True, null=True, default=None)
    # this is reserved for further use/debugging
    external_id = models.IntegerField(default=0, null=True, blank=True)
    formula = models.ForeignKey(Formula, blank=True, null=True, default=None)
    coin = models.ForeignKey(Coin)
    amount = models.FloatField(default=0)
    percents = models.IntegerField(default=100)
    # group same kind of bonuses together, using the same formula
    tag = models.CharField(max_length=64, blank=True, null=True)

    @staticmethod
    def user_coins(user):
        """ Returns a dictionary of coins and amounts for a specific user. """
        allcoins = Coin.objects.all()
        coins = {}
        for coin in allcoins:
            hs = History.objects.filter(user=user, coin=coin).aggregate(total=models.Sum('amount'))
            if hs['total'] is not None:
                coins[coin.name] = coin.format_value(hs['total'])
            else:
                if coin.is_core():
                    coins[coin.name] = 0
        return coins

    @staticmethod
    def user_points(user):
        """ :return: a list of (game, points) - distribution of points per source """
        # TODO: use user_points_from_game, but exclude empty coins
        points = {}
        for game in get_games() + [None]:
            pp = {}
            hs = History.objects.filter(user=user, game=game.get_instance() if game else game)
            for h in hs:
                if h.coin in pp.keys():
                    pp[h.coin] += h.amount
                else:
                    pp[h.coin] = h.amount
            if pp:
                if game:
                    points[game.get_instance().verbose_name] = pp
                else:
                    points['wouso'] = pp

        return points

    @staticmethod
    def user_points_from_game(user, game):
        # FIXME: add test
        game = game.get_instance() if game else game
        hs = History.objects.filter(user=user, game=game)
        pp = {}
        for c in Coin.objects.all():
            pp[c.name] = 0
        for h in hs:
            pp[h.coin.name] = pp.get(h.coin.name, 0) + h.amount
        return pp

    def __unicode__(self):
        return "{user} {date}-{formula}[{ext}]: {amount}{coin}".format(user=self.user, date=self.timestamp, formula=self.formula, ext=self.external_id, amount=self.amount, coin=self.coin)

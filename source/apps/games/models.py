from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

import trueskill

from source.apps.abstract.models import CommonModel


ts_env = trueskill.global_env()


class Rating(CommonModel):
    user = models.OneToOneField(User)
    mu = models.FloatField(default=trueskill.MU, editable=False)
    sigma = models.FloatField(default=trueskill.SIGMA, editable=False)
    exposure = models.FloatField(default=0, editable=False)

    class Meta:
        ordering = ('-exposure',)

    def save(self, *args, **kwargs):
        self.exposure = ts_env.expose(self.trueskill)
        super(Rating, self).save(*args, **kwargs)

    @property
    def trueskill(self):
        return ts_env.create_rating(mu=self.mu, sigma=self.sigma)

    def update_rating(self, outcome):
        self.mu = outcome.mu
        self.sigma = outcome.sigma
        self.save()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, signal, created, **kwargs):
    if created:
        Rating.objects.get_or_create(user=instance)


@receiver(pre_delete, sender=User)
def user_pre_delete(sender, instance, **kwargs):
    instance.rating.delete()


class Game(CommonModel):
    winner = models.ForeignKey(User, related_name='wins')
    loser = models.ForeignKey(User, related_name='losses')

    def save(self, *args, **kwargs):
        super(Game, self).save(*args, **kwargs)
        self.calculate_ratings()

    def calculate_ratings(self):
        outcomes = trueskill.rate_1vs1(
            self.winner.rating.trueskill,
            self.loser.rating.trueskill,
            env=ts_env,
        )
        self.winner.rating.update_rating(outcomes[0])
        self.loser.rating.update_rating(outcomes[1])
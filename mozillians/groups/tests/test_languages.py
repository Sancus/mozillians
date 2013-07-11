import json

from django.contrib.auth.models import User

from funfactory.urlresolvers import reverse
from nose.tools import eq_

import mozillians.common.tests.init

from mozillians.groups.cron import assign_autocomplete_to_groups
from mozillians.groups.models import AUTO_COMPLETE_COUNT, Language


class LanguagesTest(mozillians.common.tests.init.ESTestCase):

    def test_autocomplete_api(self):
        r = self.mozillian_client.get(reverse('language_search'),
                                      dict(term='daft'),
                                      HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        eq_(r['Content-Type'], 'application/json', 'api uses json header')
        assert not 'daft_punk' in json.loads(r.content)

        # Make enough users in a group to trigger the autocomplete
        robots = Language.objects.create(name='frenchie')
        for i in range(0, AUTO_COMPLETE_COUNT + 1):
            email = 'always_angry%s@example.com' % (str(i))
            user = User.objects.create_user(email.split('@')[0], email)
            user.country = 'pl'
            user.is_active = True
            user.save()
            profile = user.get_profile()
            profile.languages.add(robots)

        assign_autocomplete_to_groups()
        r = self.mozillian_client.get(reverse('language_search'),
                                      dict(term='frenchie'),
                                      HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        assert 'frenchie' in json.loads(r.content)

    def test_pending_user_can_add_languages(self):
        """Ensure pending users can add/edit languages."""
        profile = self.pending.get_profile()
        assert not profile.languages.all(), 'User should have no languages.'
        data = self.data_privacy_fields.copy()
        data.update(dict(full_name='McAwesomepants', country='pl',
                         username='McAwesomepants', languages='frenchie'))
        self.pending_client.post(reverse('profile.edit'), data, follow=True)

        assert profile.languages.all(), (
                "Pending user should be able to edit languages.")
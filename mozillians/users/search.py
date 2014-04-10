from elasticutils.contrib.django import MappingType, S
from mozillians.users.models import UserProfile
from mozillians.users.managers import MOZILLIANS
from django.conf import settings
from elasticutils.contrib.django import S

class UserProfileSearchMapping(MappingType):

    @classmethod
    def get_mapping(cls):
        """Returns an ElasticSearch mapping."""
        return {
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string', 'index': 'not_analyzed'},
                'fullname': {'type': 'string', 'analyzer': 'standard'},
                'email': {'type': 'string', 'index': 'not_analyzed'},
                'ircname': {'type': 'string', 'index': 'not_analyzed'},
                'username': {'type': 'string', 'index': 'not_analyzed'},
                'country': {'type': 'string', 'analyzer': 'whitespace'},
                'region': {'type': 'string', 'analyzer': 'whitespace'},
                'city': {'type': 'string', 'analyzer': 'whitespace'},
                'skills': {'type': 'string', 'analyzer': 'whitespace'},
                'groups': {'type': 'string', 'analyzer': 'whitespace'},
                'languages': {'type': 'string', 'index': 'not_analyzed'},
                'bio': {'type': 'string', 'analyzer': 'snowball'},
                'is_vouched': {'type': 'boolean'},
                'allows_mozilla_sites': {'type': 'boolean'},
                'allows_community_sites': {'type': 'boolean'},
                'photo': {'type': 'boolean'},
                'last_updated': {'type': 'date'},
                'date_joined': {'type': 'date'}}}

    @classmethod
    def get_model(cls):
        return UserProfile

    @classmethod
    def get_index(cls, public_index=False):
        if public_index:
            return settings.ES_INDEXES['public']
        return settings.ES_INDEXES['default']

    @classmethod
    def extract_document(cls, obj_id, obj=None):
        """Method used by elasticutils."""
        if obj is None:
            obj = cls.objects.get(pk=obj_id)
        d = {}

        attrs = ('id', 'is_vouched', 'ircname',
                 'region', 'city', 'allows_mozilla_sites',
                 'allows_community_sites')
        for a in attrs:
            data = getattr(obj, a)
            if isinstance(data, basestring):
                data = data.lower()
            d.update({a: data})

        if obj.country:
            d.update({'country':
                      [obj.country, COUNTRIES[obj.country].lower()]})

        # user data
        attrs = ('username', 'email', 'last_login', 'date_joined')
        for a in attrs:
            data = getattr(obj.user, a)
            if isinstance(data, basestring):
                data = data.lower()
            d.update({a: data})

        d.update(dict(fullname=obj.full_name.lower()))
        d.update(dict(name=obj.full_name.lower()))
        d.update(dict(bio=obj.bio))
        d.update(dict(has_photo=bool(obj.photo)))

        for attribute in ['groups', 'skills', 'languages']:
            groups = []
            for g in getattr(obj, attribute).all():
                groups.extend(g.aliases.values_list('name', flat=True))
            d[attribute] = groups
        return d

    @classmethod
    def search(cls, query, include_non_vouched=False, public=False):
        """Sensible default search for UserProfiles."""
        query = query.lower().strip()
        fields = ('username', 'bio__text', 'email', 'ircname',
                  'country__text', 'country__text_phrase',
                  'region__text', 'region__text_phrase',
                  'city__text', 'city__text_phrase',
                  'fullname__text', 'fullname__text_phrase',
                  'fullname__prefix', 'fullname__fuzzy'
                  'groups__text')
        s = PrivacyAwareS(cls)
        if public:
            s = s.privacy_level(PUBLIC)
        s = s.indexes(cls.get_index(public))

        if query:
            q = dict((field, query) for field in fields)
            s = (s.boost(fullname__text_phrase=5, username=5, email=5,
                         ircname=5, fullname__text=4, country__text_phrase=4,
                         region__text_phrase=4, city__text_phrase=4,
                         fullname__prefix=3, fullname__fuzzy=2,
                         bio__text=2).query(or_=q))

        s = s.order_by('_score', 'name')

        if not include_non_vouched:
            s = s.filter(is_vouched=True)

        return s

class PrivacyAwareS(S):

    def privacy_level(self, level=MOZILLIANS):
        """Set privacy level for query set."""
        self._privacy_level = level
        return self

    def _clone(self, *args, **kwargs):
        new = super(PrivacyAwareS, self)._clone(*args, **kwargs)
        new._privacy_level = getattr(self, '_privacy_level', None)
        return new

    def __iter__(self):
        self._iterator = super(PrivacyAwareS, self).__iter__()

        def _generator():
            while True:
                obj = self._iterator.next()
                obj._privacy_level = getattr(self, '_privacy_level', None)
                yield obj
        return _generator()

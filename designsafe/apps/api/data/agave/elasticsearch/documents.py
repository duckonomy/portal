from django.conf import settings
from elasticsearch_dsl import Search, DocType
from elasticsearch_dsl.query import Q
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl.utils import AttrList
from elasticsearch import TransportError
from designsafe.apps.api.data.agave.file import AgaveFile
import dateutil.parser
import datetime
import logging
import six
import re
import os

logger = logging.getLogger(__name__)

es_settings = getattr(settings, 'ELASTIC_SEARCH', {})

try:
    default_index = es_settings['default_index']
    cluster = es_settings['cluster']
    hosts = cluster['hosts']
except KeyError as e:
    logger.exception('ELASTIC_SEARCH missing %s' % e)

connections.configure(
    default={
        'hosts': hosts,
        'sniff_on_start': True,
        'sniff_on_connection_fail': True,
        'sniffer_timeout': 60,
        'retry_on_timeout': True,
        'timeout:': 20,
    })

class Object(DocType):
    """Class to wrap Elasticsearch (ES) documents.
        
    This class points specifically to the index `designsafe` and the 
    doc_type `objects`. This class implements most of the methods
    that the :class:`~designsafe.apps.api.data.agave.file.AgaveFile`
    class implements. Also, this class implements methods that 
    returns some predefined searches which makes talking to ES easier.

    The reason why we need this class is to keep the ES cache up-to-date
    every time we do a file operation. Meaning, that every time we do a
    file operation using the
    :class:`~designsafe.apps.api.data.agave.file.AgaveFile` we should call
    the same method on an instance of this class. 
    As we can see this class and the 
    :class:`~designsafe.apps.api.data.agave.file.AgaveFile` class share a 
    close relation. This might beg the question if they should just live
    in the same module and maybe any method of an instance of this class
    should only be called from an instance of
    :class:`~designsafe.apps.api.data.agave.file.AgaveFile`.
    The only reason I see for keeping these two classes  separated is 
    because we don't know the future of ES in our implementation. 

    .. note:: every method in this class has a `username` parameter
        this is used to construct the permissions filter. Although
        this might seem a bit insecure it is ok for now. We should
        probably look into using Shield.

    .. todo:: should this class' methods be called **only** from 
        :class:`~designsafe.apps.api.data.agave.file.AgaveFile`?
    .. todo:: create a wrapper to try/except `Unabel to sniff hosts` error.
    """
    source = 'agave'

    @classmethod
    def listing(cls, system, username, file_path):
        """Do a listing of one level.

        :param str system: system id
        :param str username: username making the request
        :param str file_path: file path to list

        :returns: list of :class:`Object`
        :rtype: list
        """
        q = {"query":{"filtered":{"query":{"bool":{"must":[{"term":{"path._exact":file_path}}, {"term": {"systemId": system}}]}},"filter":{"bool":{"should":[{"term":{"owner":username}},{"terms":{"permissions.username":[username, "world"]}}], "must_not":{"term":{"deleted":"true"}} }}}}}
        s = cls.search()
        s.update_from_dict(q)
        return cls._execute_search(s)

    @classmethod
    def from_file_path(cls, system, username, file_path):
        """Retrieves a document from the ES index based on a path.

        :param str system: system id
        :param str username: username making the request
        :param str file_path: path of a file

        :returns: instance of this class or None if the file
            doesn't exists in the index
        :rtype: :class:`Object`
        """
        path, name = os.path.split(file_path)
        path = path or '/'
        q = {"query":{"filtered":{"query":{"bool":{"must":[{"term":{"path._exact":path}},{"term":{"name._exact":name}}, {"term": {"systemId": system}}]}},"filter":{"bool":{"must_not":{"term":{"deleted":"true"}}}}}}}
        if username is not None:
            q['query']['filtered']['filter']['bool']['should'] = [{"term":{"owner":username}},{"terms":{"permissions.username":[username, "world"]}}] 

        s = cls.search()
        s.update_from_dict(q)
        res, s = cls._execute_search(s)
        if res.hits.total:
            return res[0]
        else:
            return None

    @classmethod
    def listing_recursive(cls, system, username, file_path):
        """Do a listing recursively

        This method is an efficient way to recursively do a "listing" of a 
        folder. This is because of the hierarcical tokenizer we have in 
        `path._path`. There is a caveat about this recurisve listing.
        The returned object is a list of instances of this class, but sorting
        is not ensured on this list. Sorting this list is left to the consumer
        of the api.

        :param str system: system id
        :param str username: username making the request
        :param str file_path: path of the folder to list

        :returns: list of :class:`Object`
        :rtype: list

        .. note:: sorting is not ensure on the returned list
        .. note:: the returned list does not contain the parent file

        Examples:
        ---------
            Sort listing by depth
            >>> listing = Object.listing_recursive('agave.system.id', 
            ...                     'username', 'username/path/folder')
            >>> sorted(listing, key=lambda x: len(x.full_path.split('/')))

            .. note:: Python sorting is stable. In theory we could sort the listing
                alphabetically (default behaivour) and then sort the listing
                by depth and we'll end up with a listing sorted both by depth
                and alphabetically.

        """
        q = {"query":{"filtered":{"query":{"bool":{"must":[{"term":{"path._path":file_path}}, {"term": {"systemId": system}}]}},"filter":{"bool":{"should":[{"term":{"owner":username}},{"terms":{"permissions.username":[username, "world"]}}], "must_not":{"term":{"deleted":"true"}} }}}}}
        s = cls.search()
        s.update_from_dict(q)
        return cls._execute_search(s)

    @classmethod
    def from_agave_file(cls, username, file_obj, auto_update = False, get_pems = False):
        """Get or create an ES document.

        This method accepts a :class:`~designsafe.apps.api.data.agave.file.AgaveFile`
        object and retrieves the corresponding document from the ES index.
        If the document doesn't exists in the index then it is created.
        If the document exists then that document will be returned, if `auto_update`
        is `True` the document will get upated with the 
        :class:`~designsafe.apps.api.data.agave.file.AgaveFile` object data and returned.
        If `get_pems` is `True` then an agave call to `files.listPermissions`
        is done to retrieve the file's permissions and add them to the document.

        :param str username: username making the request
        :param object file_obj: :class:`~designsafe.apps.api.data.agave.file.AgaveFile` obj
        :param bool auto_update: if set to `True` and the `file_obj` document exists
            then the document will be updated and returned
        :param bool get_pems: if set to `True` permissions will be retrieved by accessing
            `file_obj.permissions`. This usually means that an agave call will be made to
            retrieve the permissions.

        :returns: instance of this class
        :rtype: :class:`Object`

        .. note:: this is the only getter classmethod that implements a "get or create"
            behaviour. This is because we are getting the full 
            :class:`~designsafe.apps.api.data.agave.file.AgaveFile` object which 
            ensures that the document we are creating is a valid one.
        """
        o = cls.from_file_path(file_obj.system, username, file_obj.full_path)
        if o is not None:
            if auto_update:
                o.update(
                    mimeType = file_obj.mime_type,
                    name = file_obj.name,
                    format = file_obj.format,
                    deleted = False,
                    lastModified = file_obj.lastModified.isoformat(),
                    fileType = file_obj.ext or 'folder',
                    agavePath = 'agave://{}/{}'.format(file_obj.system, file_obj.full_path),
                    systemTags = [],
                    length = file_obj.length,
                    systemId = file_obj.system,
                    path = file_obj.parent_path,
                    keywords = [],
                    link = file_obj._links['self']['href'],
                    type = file_obj.type
                )
            if get_pems:
                o.update(permissions = file_obj.permissions)
            return o

        o = cls(
            mimeType = file_obj.mime_type,
            name = file_obj.name,
            format = file_obj.format,
            deleted = False,
            lastModified = file_obj.lastModified.isoformat(),
            fileType = file_obj.ext or 'folder',
            agavePath = 'agave://{}/{}'.format(file_obj.system, file_obj.full_path),
            systemTags = [],
            length = file_obj.length,
            systemId = file_obj.system,
            path = file_obj.parent_path,
            keywords = [],
            link = file_obj._links['self']['href'],
            type = file_obj.type
        )
        o.save()
        if get_pems:
            pems = file_obj.permissions
        else:
            path = file_obj.path
            pems_user = path.strip('/').split('/')[0]
            pems = [{
                'username': pems_user,
                'recursive': True,
                'permission': {
                    'read': True,
                    'write': True,
                    'execute': True
                }
            }]

        o.update(permissions = pems)
        o.save()
        return o

    @staticmethod        
    def _execute_search(s):
        """Method to try/except a search and retry if the response is something
            other than a 404 error.

        :param object s: search object to execute

        .. todo:: this should probably be a wrapper so we can use it everywhere.
        """
        try:
            res = s.execute()
        except TransportError as e:
            if e.status_code == 404:
                raise
            res = s.execute()
        return res, s

    def copy(self, username, path):
        """Copy a document.

        Although creating a copy of a document using this class is farily 
        straight forward (i.e. `o = Object(**doc); o.save()`, this method
        is necessary in order to account for recursive copying i.e. when
        a folder is copied.

        :param str username: username making the request
        :param str path: path to the file to copy

        :returns: instance of this class
        :rtype: :class:`Object`

        .. note:: this method returns the copied document.

        Examples:
        ---------
            Copy a file and print the resulting copied file path

            >>> origin_doc = Object.from_file_path('agave.system.id', 
            ...                 'username', 'username/path/file.txt')
            >>> origin_doc.copy('username', 'file_copy.txt')
            >>> #we have to go and search the resulting document
            >>> copied_doc = Object.from_file_path(origin_doc.systemId,
            ...           'username', os.path.join(origin_doc.path, 'file_copy.txt')
            >>> print 'resulting file path: {}'.format(copied_doc.full_path)
        """
        #split path arg. Assuming is in the form /file/to/new_name.txt
        tail, head = os.path.split(path)
        #check if we have something in tail.
        #If we don't then we got just the new file name in the path arg.
        if tail == '':
            head = path
        if self.type == 'dir':
            res, s = self.__class__.listing_recursive(self.systemId, username, os.path.join(self.path, self.name))
            for o in s.scan():
                d = o.to_dict()
                regex = r'^{}'.format(os.path.join(self.path, self.name))
                d['path'] = re.sub(regex, os.path.join(self.path, head), d['path'], count = 1)
                d['agavePath'] = 'agave://{}/{}'.format(self.systemId, os.path.join(d['path'], d['name']))
                doc = Object(**d)
                doc.save()
        d = self.to_dict()
        d['name'] = head
        d['agavePath'] = 'agave://{}/{}'.format(self.systemId, os.path.join(d['path'], d['name']))
        doc = Object(**d)
        doc.save()
        self.save()
        return doc

    def delete_recursive(self):
        """Delete a file recursively.

        This method works with both files and folders.
        If the document represents a folder then it will 
        recursively delete any childre documents.

        :returns: count of how many documents were deleted
        :rtype: int
        """
        cnt = 0
        if self.type == 'dir':
            res, s = self.__class__.listing_recursive(self.systemId, username, os.path.join(self.path, self.name))
            for o in s.scan():
                o.delete()
                cnt += 1

        self.delete()
        cnt += 1
        return cnt

    @property
    def ext(self):
        """Returns the extension of a file.

        :returns: extension in the form `.[a-z]+` **note the dot**
        :rtype: str
        """
        return os.path.splitext(self.name)[1]

    @property
    def full_path(self):
        """Returns the full path of a file

        :returns: full path of a file
        :rtype: str
        """
        return os.path.join(self.path, self.name)

    def move(self, username, path):
        """Update document with new path

        :param str username: username making the request
        :param str path: path to update

        :returns: an instance of this class
        :rtype: :class:`Object`
        """
        if self.type == 'dir':
            res, s = self.__class__.listing_recursive(self.systemId, username, os.path.join(self.path, self.name))
            for o in s.scan():
                regex = r'^{}'.format(os.path.join(self.path, self.name))
                o.update(path = re.sub(regex, os.path.join(path, self.name), o.path, count = 1))
                o.update(agavePath = 'agave://{}/{}'.format(self.systemId, os.path.join(self.path, self.name))) 

        tail, head = os.path.split(path)
        self.update(path = tail)
        self.update(agavePath = 'agave://{}/{}'.format(self.systemId, os.path.join(self.path, self.name)))
        logger.debug('Moved: {}'.format(self.to_dict()))
        self.save()
        return self


    def rename(self, username, path):
        """Updates a document with a new name.

        :param str username: username making the request
        :param str path: name to upate

        :returns: an instance of this class
        :rtype: :class:`Object`
        """
        #split path arg. Assuming is in the form /file/to/new_name.txt
        tail, head = os.path.split(path)
        #check if we have something in tail.
        #If we don't then we got just the new file name in the path arg.
        if tail == '':
            head = path       
        if self.type == 'dir':
            res, s = self.__class__.listing_recursive(self.systemId, username, os.path.join(self.path, self.name))
            for o in s.scan():
                regex = r'^{}'.format(os.path.join(self.path, self.name))
                o.update(path = re.sub(regex, os.path.join(self.path, head), o.path, count = 1))
                o.update(agavePath = 'agave://{}/{}'.format(self.systemId, os.path.join(self.path, head)))
                logger.debug('Updated document to {}'.format(os.path.join(o.path, o.name)))
        self.update(name = head)
        self.update(agavePath = 'agave://{}/{}'.format(self.systemId, os.path.join(self.path, head)))
        logger.debug('Updated ocument to {}'.format(os.path.join(self.path, self.name)))
        self.save()
        return self

    def share(self, username, user_to_share, permission):
        """Update permissions on a document recursively.

        :param str username: username making the request
        :param str user_to_share: username with whom we are going to share this document
        :param str permission: string representing the permission to set 
            [READ | WRITE | EXECUTE | READ_WRITE | READ_EXECUTE | WRITE_EXECUTE | ALL | NONE]
        """
        if self.type == 'dir':
            res, s = self.__class__.listing_recursive(self.system, username, os.path.join(self.path, self.naem))
            for o in s.scan():
                o.update_pems(user_to_share, permission)
        
        path_comps = os.path.join(self.path, self.name).split('/')
        path_comps.pop()
        for i in range(len(path_comps)):
            doc_path = '.'.join(path_comps)
            doc = Object.from_file_path(self.systemId, username, doc_path)
            doc.update_pems(user_to_share, permission)
            path_comps.pop()

        self.update_pems(user_to_share, permission)
        self.save()
        return self

    def update_pems(self, user_to_share, pem):
        pems = getattr(self, 'permissions', [])
        pem_to_add = {
                'username': user_to_share,
                'recursive': True,
                'permission': {
                    'read': True if pem in ['READ_WRITE', 'READ_EXECUTE', 'READ', 'ALL'] else False,
                    'write': True if pem in ['READ_WRITE', 'WRITE_EXECUTE', 'WRITE', 'ALL'] else False,
                    'execute': True if pem in ['READ_EXECUTE', 'WRITE_EXECUTE', 'EXECUTE', 'ALL'] else False
                }
            }
        user_pems = filter(lambda x: x['username'] != user_to_share, pems)
        user_pems.append(pem_to_add)
        self.update(permissions = user_pems)
        self.save()
        return self
        
    def to_file_dict(self):
        """Returns a dictionary correctly formatted
            as a data api response.

        This method first constructs a dictionary that looks like
        a response from an agave call to `files.listing`. After this
        it instantiates a :class:`~designsafe.apps.api.agave.files.AgaveFile` object
        and returns the result of :meth:`~designsafe.apps.api.agave.files.AgaveFile.to_dict`.
        We hand off the dict construction to the 
        :class:`~designsafe.apps.api.agave.files.AgaveFile` class so we don't have to
        implement it twice. 

        :returns: dict object representation of a file
        :rtype: dict

        .. note:: in future releases the ES documents in the index should look like
            the response of an agave call to `files.listing`. We would need to keep
            this method to hand of the dict construction to the
            :class:`~designsafe.apps.api.agave.files.AgaveFile` class
        """
        try:
            lm = dateutil.parser.parse(self.lastModified)
        except AttributeError:
            lm = datetime.datetime.now()

        wrap = {
            'format': getattr(self, 'format', 'folder'),
            'lastModified': lm,
            'length': self.length,
            'mimeType': self.mimeType,
            'name': self.name,
            'path': os.path.join(self.path, self.name).strip('/'),
            'permissions': self.permissions,
            'system': self.systemId,
            'type': self.type,
            '_permissions': self.permissions
        }
        f = AgaveFile(wrap = wrap)
        return f.to_dict()

    class Meta:
        index = default_index
        doc_type = 'objects'

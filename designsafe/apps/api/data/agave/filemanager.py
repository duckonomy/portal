from agavepy.agave import AgaveException, Agave
from agavepy.async import AgaveAsyncResponse, TimeoutError, Error
from designsafe.apps.api.exceptions import ApiException
from designsafe.apps.api.data.agave.agave_object import AgaveObject
from designsafe.apps.api.data.agave.file import AgaveFile
from designsafe.apps.api.data.abstract.filemanager import AbstractFileManager
from designsafe.apps.api.data.agave.elasticsearch.documents import Object
from django.conf import settings
from django.core.urlresolvers import reverse
from functools import wraps
import os
import logging
logger = logging.getLogger(__name__)

FILESYSTEMS = {
    'default': getattr(settings, 'AGAVE_STORAGE_SYSTEM')
}

class FileManager(AbstractFileManager, AgaveObject):

    resource = 'agave'

    def __init__(self, user_obj, **kwargs):
        """Intializes an instance of the class.

        the `__init__` method of the superclass is called because
        this class subclasses AgaveObject which sets `self.agave_client`
        AND `self._wrap`. The latter is not used in this class.
        Here we're only initializing the agave client.

        :param str user_obj: The user object from the django user model.
        """
        super(FileManager, self).__init__(**kwargs)
        username = user_obj.username
        if user_obj.agave_oauth.expired:
            user_obj.agave_oauth.refresh()

        token = user_obj.agave_oauth
        access_token = token.access_token
        agave_url = getattr(settings, 'AGAVE_TENANT_BASEURL')
        self.agave_client = Agave(api_server = agave_url, 
                                  token = access_token)
        self.username = username

    def is_shared(self, file_id):
        """Checks if the `file_id` is shared for the file manager's user.

        TODO: Should this be a static method? or an AgaveFile's 
              method `AgaveFile.check_shared(user, file_id)`

        :param str file_id: File identificator

        :return: True if the file is shared with the current user. 
                 Otherwise False
        :rtype: bool

        Notes:
        -----

            The check is if the file is in the default agave storage system
            and if the file lives in the user's home directory. If both of
            these checks are False then it is assumed is a shared file for
            the user.
        """
        file_id = self.parse_file_id(file_id)
        return not (file_id[0] == settings.AGAVE_STORAGE_SYSTEM and file_id[1] == self.username)
    
    def _agave_listing(self, system, file_path):
        """Returns a "listing" dict constructed with the response from Agave.

        :param str sytem: System id
        :param str file_path: Path to list

        :returns: A dict with information of the listed file and, when possible, 
        a list of :class:`~designsafe.apps.api.data.agave.files.AgaveFile` objects
        dict in the key ``children``
        :rtype: dict

        Notes:
        -----

            This should not be called directly. See py:meth:`listing(file_id)`
            for more information.
        """
        listing = AgaveFile.listing(system, file_path, self.agave_client)
        #logger.debug('listing: {}'.format(listing))

        root_file = filter(lambda x: x.full_path == file_path, listing)
        #logger.debug('root_file: {}'.format(root_file[0]))

        list_data = root_file[0].to_dict()
        list_data['children'] = [o.to_dict() for o in listing if o.full_path != file_path]

        return list_data

    def _es_listing(self, system, username, file_path):
        """Returns a "listing" dict constructed with the response from Elasticsearch.

        :param str system: system id
        :param str username: username which is requesting the listing. 
                             This is to check the permissions in the ES docs.
        :param str file_path: path to list

        :returns: A dict with information of the listed file and, when possible, 
        a list of :class:`~designsafe.apps.api.data.agave.elasticsearch.documents.Object` objects
        dict in the key ``children``
        :rtype: dict

        Notes:
        -----

            This should not be called directly. See py:meth:`listing(file_id)`
            for more information.
        """
        res, listing = Object.listing(system, username, file_path)
        root_listing = Object.from_file_path(system, username, file_path)

        if system == settings.AGAVE_STORAGE_SYSTEM and file_path == '/':
            list_data = {
                '_tail': [],
                '_actions': [],
                '_pems': [],
                'source': self.resource,
                'id': '$share',
                'system': settings.AGAVE_STORAGE_SYSTEM,
                'path': '',
                'name': '$SHARE',
                'children': [o.to_file_dict() for o in listing.scan() if o.name != username]
            }
        else:
            list_data = root_listing.to_file_dict()
            list_data['children'] = [o.to_file_dict() for o in listing.scan()]
        return list_data

    def parse_file_id(self, file_id):
        """Parses a `file_id`.

        :param str file_id: String with the format 
        <filesystem id>[ [ [/ | /<username> [/ | /<file_path>] ] ] ]

        :returns: a list with three elements

            * index 0 `system_id`: String. Filesystem id 
            * index 1 `file_user`: String. Home directory's username of the 
                                 file the `file_id` points to.
            * index 2 `file_path`: String. Complete file path.
        :rtype: list

        :raises ValueError: if the object is not in the desired format

        Examples:
        --------
            `file_id` can look like this:
              `designsafe.storage.default`:
              Points to the root folder in the 
              `designsafe.storage.default` filesystem.

              `designsafe.stroage.default/username`:
              Points to the home directory of the user `username`.

              `designsafe.storage.default/username/folder`:
              Points to the folder `folder` in the home directory
              of the user `username`.

              `designsafe.stroage.default/username/folder/file.txt`:
              Points to the file `file.txt` in the home directory
              of the username `username`
        """
        if file_id is None or file_id == '':
            system_id = settings.AGAVE_STORAGE_SYSTEM
            file_path = self.username
            file_user = self.username
        else: 
            components = file_id.strip('/').split('/')
            system_id = components[0] if len(components) >= 1 else None
            file_path = '/'.join(components[1:]) if len(components) >= 2 else self.username
            file_user = components[1] if len(components) >= 2 else self.username

        return system_id, file_user, file_path
        
    def listing(self, file_id, **kwargs):
        """
        Lists contents of a folder or details of a file.

        :param str file_id: id representing the file. Format:
        <filesystem id>[ [ [/ | /<username> [/ | /<file_path>] ] ] ]

        :returns:listing dict. A dict with the properties of the 
        parent path file object plus a `childrens` key with a list
        of :class:`~.
        If the `file_id` passed is a file and not a folder the 
        `children` list will be empty.
        :rtype: dict

        Examples:
            A listing dictionary:
            ```{
                  _pems: [ ],
                  type: "folder",
                  path: "",
                  id: "designsafe.storage.default/path/folder",
                  size: 32768,
                  name: "username",
                  lastModified: "2016-04-26T22:25:30-0500",
                  system: "designsafe.storage.default",
                  children: [],
                  source: "agave",
                  ext: "",
                  _actions: [ ],
                  _trail: [ ]
                }
            ```

            To loop through the listing's files:
            >>> listing = fm.listing(**kwargs)
            >>> for child in listing['children']: 
            >>>     do_something_cool(child)
        """
        system, file_user, file_path = self.parse_file_id(file_id)
        #if file_path.lower() == '$share':
        #    file_path = '/'
        #    file_user = self.username
        #listing = self._es_listing(system, self.username, file_path)
        #if not listing:
        #    listing = self._agave_listing(system, file_path)
        listing = self._agave_listing(system, file_path)
        return listing

    def search(self, **kwargs):
        return [{}]

    def copy(self, system, file_path, file_user, path, **kwargs):
        """Copies a file

        Copies a file in both the Agave filesystem and the 
        Elasticsearch index.
            
        :param str system: system id
        :param str file_path: full path to the file to copy
        :param str file_user: username of the owner of the file
        :param str path: full path to the resulting copied file

        :returns: dict representation of the original 
        :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict

        Examples:
        --------
            Copy a file. `fm` is an instance of FileManager
            >>> fm.copy(system = 'designsafe.storage.default' 
            >>>         file_path = 'username/file.jpg', 
            >>>         file_user = 'username', 
            >>>         path = 'username/file_copy.jpg')
        """
        f = AgaveFile.from_file_path(system, self.username, file_path,
                    agave_client = self.agave_client)
        f.copy(path)
        esf = Object.from_file_path(system, self.username, file_path)
        esf.copy(self.username, path)
        return f.to_dict()

    def delete(self, system, file_path, file_user, **kwargs):
        """Deletes a file

        Deletes a file in both the Agave filesystem and the
        Elasticsearch index.

        :param str system: system id
        :param str file_path: full path to the file to copy
        :param str file_user: username of the owner of the file

        :returns: dict representation of the target 
        :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict
        
        Examples:
        --------
            Delete a file. `fm` is an instance of FileManager
            >>> fm.delete(system = 'designsafe.storage.default' 
            >>>         file_path = 'username/.Trash/file.jpg', 
            >>>         file_user = 'username')
        """
        f = AgaveFile.from_file_path(system, self.username, file_path,
                    agave_client = self.agave_client)
        f.delete()
        esf = Object.from_file_path(system, self.username, file_path)
        esf.delete_recursive()
        return f.to_dict()

    def download(self, file_id, **kwargs):
        """Get the download link for a file

        :param str file_id: String with the format 
        <filesystem id>[ [ [/ | /<username> [/ | /<file_path>] ] ] ]

        :returns: a dict with a single key `href` which has the direct
            noauth link to download a file
        :rtype: dict

        """
        system, file_user, file_path = self.parse_file_id(file_id)

        f = AgaveFile.from_file_path(system, self.username, file_path, 
                    agave_client = self.agave_client)
        postit = f.create_postit(force=True)
        return {'href': postit['_links']['self']['href']}

    def file(self, file_id, action, path = None, **kwargs):
        """Main routing method for file actions
        
        :param str file_id: String with the format 
            <filesystem id>[ [ [/ | /<username> [/ | /<file_path>] ] ] ]
        :param str action: action to execute. Must be a valid method name
        :param str path: target path to use. Optional

        :returns: see the independent methods for the returned value. Usually
            the return value is a dict representation of the file to which the
            operation is being applied.

        Notes:
        -----
            This method should be used when doing any of these file operations:

                * copy
                * delete
                * move
                * move_to_trash
                * mkdir
                * rename
                 
            The `action` param should be any of the previous operations.                 
        """
        system, file_user, file_path = self.parse_file_id(file_id)

        file_op = getattr(self, action)
        return file_op(system, file_path, file_user, path, **kwargs)

    def move(self, system, file_path, file_user, path, **kwargs):
        """Move a file

        Moves a file both in the Agave filesystem and the
        Elasticsearch index.

        :param str system: system id
        :param str file_path: full path to the file to move
        :param str file_user: username of the owner of the file
        :param str path: full path to move the file

        :returns: dict representation of the  
            :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict
        """
        f = AgaveFile.from_file_path(system, self.username, file_path, 
                    agave_client = self.agave_client)
        f.move(path)
        esf = Object.from_file_path(system, self.username, file_path)
        esf.move(self.username, path)
        return f.to_dict()

    def move_to_trash(self, system, file_path, file_user, **kwargs):
        """Move a file into the trash folder

        Moves a file both in the Agave filesystem and the
        Elasticsearch index.

        :param str system: system id
        :param str file_path: full path to the file to move
        :param str file_user: username of the owner of the file

        :returns: dict representation of the  
            :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict
        """
        trash = Object.from_file_path(system, self.username, 
                                os.path.join(self.username, '.Trash'))
        if trash is None:
            f_dict = self.mkdir(system, self.username, file_user, 
                            os.path.join(self.username, '.Trash'), **kwargs) 
        tail, head = os.path.split(file_path)
        ret = self.move(system, file_path, file_user, os.path.join(self.username, '.Trash', head))
        return ret

    def mkdir(self, system, file_path, file_user, path, **kwargs):
        """Creatd a directory

        Creates a directory both in the Agave filesystem and the
        Elasticsearch index.

        :param str system: system id
        :param str file_path: full path to where the directory will be created
        :param str file_user: username of the owner of the file
        :param str path: full path to the directory to create

        :returns: dict representation of the  
            :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict

        Examples:
        --------
            Creating a directory `mkdir_test` in the $HOME directory
            of the user `username`
            >>> fm.mkdir(system = 'designsafe.storage.default'
            >>>          file_path = 'username', 
            >>>          file_user = 'username',
            >>>          path = 'username/mkdir_test')
        """
        f = AgaveFile.mkdir(system, self.username, file_path, path,
                    agave_client = self.agave_client)
        logger.debug('f: {}'.format(f.to_dict()))
        esf = Object.from_agave_file(self.username, f)
        return f.to_dict()

    def preview(self, file_id, **kwargs):
        logger.debug(kwargs)
        system, file_user, file_path = self.parse_file_id(file_id)

        f = AgaveFile.from_file_path(system, self.username, file_path,
                    agave_client = self.agave_client)

        if f.previewable:
            fmt = kwargs.get('format', 'json')
            if fmt == 'html':
                context = {}
                if f.ext in AgaveFile.SUPPORTED_IMAGE_PREVIEW_EXTS:
                    postit = f.create_postit(force=False)
                    context['image_preview'] = postit['_links']['self']['href']
                elif f.ext in AgaveFile.SUPPORTED_TEXT_PREVIEW_EXTS:
                    content = f.download()
                    context['text_preview'] = content
                elif f.ext in AgaveFile.SUPPORTED_OBJECT_PREVIEW_EXTS:
                    postit = f.create_postit(force=False)
                    context['object_preview'] = postit['_links']['self']['href']
                return 'designsafe/apps/api/data/agave/preview.html', context
            else:
                preview_url = reverse('designsafe_api:file',
                                      args=[self.resource, file_id]
                                      ) + '?action=preview&format=html'
                return {'href': preview_url}
        else:
            return None

    def rename(self, system, file_path, file_user, path, **kwargs):
        """Renames a file

        Renames a file both in the Agave filesystem and the
        Elasticsearch index.

        :param str system: system id
        :param str file_path: full path to the file
        :param str file_user: username of the owner of the file
        :param str path: new name for the file

        :returns: dict representation of the  
            :class:`designsafe.apps.api.data.agve.file.AgaveFile` instance
        :rtype: dict

        Notes:
        ------
            `path` should only be the name the file will be renamed with.
        """
        f = AgaveFile.from_file_path(system, self.username, file_path,
                    agave_client = self.agave_client)
        f.rename(path)
        esf = Object.from_file_path(system, self.username, file_path)
        esf.rename(self.username, path)
        return f.to_dict()
    
    def share(self, file_id, user = '', permission = 'READ', **kwargs):
        """Update permissions for a file

        The default functionality is to set READ permission on the file
        for the specified user

        :param str file_id: string with the format
            <filesystem id>[ [ [/ | /<username> [/ | /<file_path>] ] ] ]
        :param str permission: permission to set on the file [READ | WRITE |
            EXECUTE | READ_WRITE | READ_EXECUTE | WRITE_EXECUTE | ALL | NONE]

        Notes:
        -----
            If the target file is a directory then it will set the permissions
            recursively
        """
        system, file_user, file_path = self.parse_file_id(file_id)

        f = AgaveFile.from_file_path(system, self.username, file_path,
                    agave_client = self.agave_client)
        f.share(user, permission)
        esf = Object.from_file_path(system, self.username, file_path)
        esf.share(self.username, user, permission)
        return f.to_dict()

class AgaveIndexer(AgaveObject):
    """Indexer class for all indexing needs.
    
    This class helps when indexing files/folders into elasticsearch.
    A file/folder needs to be indexed after any change except for content changes.
    Meaning, when a file/folder is created, renamed, moved, etc.

    It is recommended to call any of this class' methods in a celery task.
    This is because most of the indexing operations take a 
    considerable amount of time.

    **Disclaimer:** A class is used to pack all this functionality together.
    This is not necessary and these methods should, probably, live in a separate
    module. The decision to leave this class here, for now, is because of the close
    relation the indexing operations have with the :class:`filemanager` operations.

    Generators
    ---------

        There are two generators implemented in this class 
        :meth:`walk` and :meth:`walk_levels`. The functionality of these generators
        is based on :meth:`os.walk` and their intended use is the same.
        
        :met:`walk_levels` is similar to :met:`os.walk`. This is the prefered
        method to walk an Agave filesystem. 

        :meth:`walk` differs from the regular :meth:`os.walk` in that it returns
        a single file on every iteration instead of lists of `files` and `folders`.
        This implementation is mainly legacy and was the first approach to walking
        an agave filesyste that we tried. It is recommended to use 
        :meth:`walk_levels` since it is more efficient. :met:`walk` can 
        still be used, preferably, if the folder to walk is small.

    Indexing
    --------

        There are three different methods for indexing :meth:`index`, :meth:`index_full`
        and :met:`index_permissions`. The speration is necessary due to the number of
        calls necessary to get all the information needed. If we want to retrieve
        all the information for a specific file from agave (file information and 
        permissions) we need to to a `files.listing` call and a `files.pems` call.
        Retrieving the permissions is a separate call because Agave calculates
        the permissions of a file based on different rules stored in the database. 
        This need for two calls drives us to use "optimistic permissions" when ever
        possible. "optimistic permissions" is when we assume who the owner of the
        file is going to be and create a permission object with the owner's username
        instead of making another call to Agave. The owner's username is extracted
        from the target file path. We assume a file path of $HOME/path/to/file.txt
        where $HOME will always be the username of the owner.
    """

    def walk(self, system_id, path, bottom_up = False, yield_base = True):
        """Walk a path in an agave filesystem.

        This generator will yield single :class:`~designsafe.apps.api.agave.file.AgaveFile` 
        object at a time. A call to `files.list` is done for every sub-level of `path`.
        For a more efficient approach see :meth:`walk_levels`.

        :param str system_id: system id
        :param str path: path to walk
        :param bool bottom_up: if `True` walk the path bottom to top. Default `False`
            will walk the path top to bottom
        :param bool yield_base: if 'True' will yield an 
            :class:`~designsafe.apps.api.agave.file.AgaveFile` object of the 
            path walked in the first iteration. After the first iteration it will
            yield the children objects. Default 'True'.

        :returns: childrens of the given file path
        :rtype: :class:`~designsafe.apps.api.agave.file.AgaveFile`

        Pseudocode:
        -----------

        1. call `files.list` on `path`
        2. for each file in the listing
            
            2.1. instantiate :class:`~designsafe.apps.api.agave.file.AgaveFile`
            2.2. check if we need to yield the parent folder
            2.3. yield the :class:`~designsafe.apps.api.agave.file.AgaveFile`
                instance if walking top to bottom
            2.4. if it is a folder

                2.4.1. call :met:`walk` with the folder's path
                2.4.1. yield the object
            
            2.3. yield the :class:`~designsafe.apps.api.agave.file.AgaveFile`
                instance if walking bottom to top

        """
        files = self.call_operation('files.list', systemId = system_id, 
                                    filePath = path)
        for f in files:
            aff = AgaveFile(agave_client = self.agave_client, wrap = f)
            if f['name'] == '.' or f['name'] == '..':
                if not yield_base:
                    continue
            if not bottom_up:
                yield aff
            if aff.format == 'folder' and f['name'] != '.':
                for sf in self.walk(system_id, aff.full_path, bottom_up = bottom_up, yield_base = False):
                    yield sf
            if bottom_up:
                yield aff

    def walk_levels(self, system_id, path, bottom_up = False):
        """Walk a path in an agave filesystem.

        This generator walks the agavefilesystem making a call to `files.list`
        for each sub-level of the given path. This generator differs from 
        :meth:`walk` in that it returns all files and folders in a level
        instead of a single file at a time. This behaviour is closer to
        that of :meth:`os.walk`

        :param str system_id: system id
        :param str path: path to walk
        :param bool bottom_up: if `True` walk the path bottom to top. Default `False`
            will walk the path top to bottom

        :returns: A triple with the root fiele path string, a list with all the
            folders in the current level and a list with all the files in the 
            current level.
        :rtype: (`str` root, 
            [:class:`~designsafe.apps.api.agave.file.AgaveFile`] folders, 
            [:class:`~designsafe.apps.api.agave.file.AgaveFile`] files)

 
        Pseudocode:
        -----------

        1. call `files.list` on `path`
        2. for each file in the listing
            
            2.1. instantiate :class:`~designsafe.apps.api.agave.file.AgaveFile`
            2.2. append object to the corresponding folders or files list
        
        3. if is a top to bottom walk then yield (path, folders, files)
        4. for every folder in `folders`
            
            4.1. yield returned triple from calling :meth:`walk_levels` 
                using the folder's path
        
        5. if is a bottom to top walk then yield (path, folders, files)

        Notes:
        ------
            
            Similar to :meth:`os.walk` the `files` and `folders` list can be
            modified inplace to modify future iterations. Modifying the
            `files` and `folders` lists inplace can be used to tell the
            generator of any modifications done with every iteration.
            This only makes sense when `bottom_up` is `False`. Any inplace 
            change to the `files` or `folders` list when `bottom_up` is 
            `True` it will not affect the behaviour of the yielded objects.

        Examples:
        ---------

            Only walk a specific number of levels

            >>> levels = 2
            >>> for root, folders, files in self.walk_levels('designsafe.storage.default', 
            ... 'username'):
            >>>     #do cool things
            >>>     #first check if we are at the necessary level
            >>>     if levels and len(root.split('/')) >= levels:
            ...         #delete everything from the folders list
            ...         #so the generator will stop recursing
            ...         del folders[:]

        """

        resp = self.call_operation('files.list', systemId = system_id,
                                    filePath = path)
        folders = []
        files = []
        for f in resp:
            if f['name'] == '.':
                continue
            aff = AgaveFolderFile(self.agave_client, f)
            if aff.format == 'folder':
                folders.append(aff)
            else:
                files.append(aff)
        if not bottom_up:
            yield (path, folders, files)
        for aff in folders:
            for (spath, sfolders, sfiles) in self.walk_levels(system_id, aff.full_path, bottom_up = bottom_up):
                yield (spath, sfolders, sfiles)

        if bottom_up:
            yield (path, folders, files)

    def _dedup_and_discover(system_id, username, root, files, folders):
        """Deduping and discovery of Agave Files in Elasticsearch (ES)

        This helper function process a list of folders and files to discover
        new file objects that haven't been indexed in ES. Also, dedups 
        objects saved to the ES index.

        :pram str system_id: system id
        :param str username: the owner's username of the path being indexed
        :param str root: root path
        :param list files: a list of :class:`~designsafe.apps.api.data.agave.file.AgaveFile` objects
        :param list folders: a list of :class:`~designsafe.apps.api.data.agave.file.AgaveFile` objects

        :returns: `(objs_to_index, docs_to_delete)` A tuple with two lists 
            `objs_to_index` is a list of :class:`~designsafe.apps.api.data.agave.file.AgaveFile` 
            objects for which no ES object was found with the same `path` + `name`.
            `docs_to_delete` is a list of 
            :class:`~designsafe.apps.api.agave.elasticsearch.document.Object` objects
            which appear repeated in the ES index.
        :rtype: tuple of lists

        Pseudocode
        ----------
            
            1. construct a list of all the file names. This is so we can use it
                to compare the documents retrieved from ES. We use only the 
                file name because we are operating on a specific filesystem level
                meaning that the path is always going to be the same.
            2. get all the documents that are direct children of the root path given.
            3. for each document retrieved from ES

                3.1. append document to the list of documents
                3.2. if the name of the document is already in the list of 
                    document names then we assume is a duplicate and append it
                    to the list of documents to delete.
                    If the name of the document is not in the list of document
                    names then append it
            
            4. create the `objs_to_index` list by getting all the file objects 
                which names do not appear in the list of document names. Meaning,
                we are getting all the file objects that we do not have in the
                ES index.
            5. create the `docs_to_delete` list by appending all the documents
                which names do not appear in the file object names list to the
                previously creatd duplicated documents list. Meaning, we are
                appending all the ES documents for which there are no file in the
                agave filesystem.
        """

        objs = folders + files
        objs_names = [o.name for o in objs]
        r, s = Object.listing(system_id, username, root)
        docs = []
        doc_names = [] 
        docs_to_delete = []

        for d in s.scan():
            docs.append(d)
            if d.name in doc_names:
                docs_to_delete.append(d)
            else:
                doc_names.append(d.name)
        objs_to_index = [o for o in objs if o.name not in doc_names]
        docs_to_delete += [o for o in docs if o.name not in objs_names]
        return objs_to_index, docs_to_delete

    def index(self, system_id, path, username, bottom_up = False, levels = 0, index_full_path = True):
        for root, folders, files in self.walk_levels(system_id, path, bottom_up = bottom_up):
            objs_to_index, docs_to_delete = self._dedup_and_discover(system_id, 
                                                username, root, files, folders)
            for o in objs_to_index:
                d = o.to_dict(pems = False)
                pems_user = d['path'].split('/')[0] if d['path'] != '/' else d['name']
                d['permissions'] = [{
                    'username': pems_user,
                    'recursive': True,
                    'permission': {
                        'read': True,
                        'write': True,
                        'execute': True
                    }
                }]
                do = Object(**d)
                do.save()

            for d in docs_to_delete:
                #print dir(d)
                #print d.path + '/' + d.name
                d.delete()
                if d.format == 'folder':
                    r, s = Object().search_exact_folder_path(system_id, username, os.path.join(d.path, d.name))
                    for doc in s.scan():
                        doc.delete()

            #logger.debug('levels {} cnt {}'.format(levels, cnt))
            if levels and len(root.split('/')) >= levels:
                del folders[:]

        if index_full_path:
            paths = path.split('/')
            for i in range(len(paths)):
                path = '/'.join(paths[:-1])
                name = paths[-1]
                logger.info('checking {}'.format(paths))
                if not Object().get_exact_path(system_id, username, path, name):
                    fo = AgaveFolderFile.from_path(self.agave_client, system_id, os.path.join(path, name))
                    o = Object(**fo.to_dict(pems = False))
                    o.save()
                    pems_user = o.path.split('/')[0] if o.path != '/' else o.name
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
                paths.pop()

    def index_full(self, system_id, path, username, bottom_up = False, levels = 0, index_full_path = True):
        for root, folders, files in self.walk_levels(system_id, path, bottom_up = bottom_up):
            objs = folders + files
            for o in objs:
                d = Object(**o.to_dict())
                d.save()
            if levels and len(root.path('/')) >= levels:
                del folders[:]

        if index_full_path:
            paths = path.split('/')
            for i in range(len(paths)):
                path = '/'.join(paths[:-1])
                name = paths[-1]
                fo = AgaveFolderFile.from_path(self.agave_client, system_id, os.path.join(path, name))
                o = Object(**fo.to_dict())
                o.save()
                paths.pop()

    def index_permissions(self, system_id, path, username, bottom_up = True, levels = 0):
        r, s = Object().search_partial_path(system_id, username, path)
        objs = sorted(s.scan(), key = lambda x: len(x.path.split('/')), reverse=bottom_up)
        if levels:
            objs = filter(lambda x: len(x.path.split('/')) <= levels, objs)
        p, n = os.path.split(path)
        if p == '':
            p = '/'
        objs.append(Object().get_exact_path(system_id, username, p, n))
        for o in objs:
            if len(o.path.split('/')) == 1 and o.name == 'Shared with me':
                continue
            pems = self.call_operation('files.listPermissions', filePath = urllib.quote(os.path.join(o.path, o.name)), systemId = system_id)
            o.update(permissions = pems)


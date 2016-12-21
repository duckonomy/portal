"""Main views for sitewide search data. api/search/?*
   All these views return :class:`JsonResponse`s
   These should be general enough to handle various type of public data
   and for authenticated users any private data that they can
   access.
"""
from pprint import pprint
import logging
import json
from elasticsearch_dsl import Q, Search
from django.http import (HttpResponseRedirect,
                         HttpResponseServerError,
                         JsonResponse)
from designsafe.apps.api.views import BaseApiView
from designsafe.apps.api.mixins import SecureMixin
from designsafe.apps.api.agave.filemanager.public_search_index import (
    PublicElasticFileManager, PublicObjectIndexed, connections,
    PublicFullIndexed, CMSIndexed,
    PublicProjectIndexed, PublicExperimentIndexed)

logger = logging.getLogger(__name__)

class SearchView(BaseApiView):
    """Main view to handle sitewise search requests"""
    def get(self, request):
        """GET handler."""
        q = request.GET.get('q')
        system_id = PublicElasticFileManager.DEFAULT_SYSTEM_ID
        offset = int(request.GET.get('offset', 0))
        limit = int(request.GET.get('limit', 10))

        web_query = Search(index="cms")\
            .query("query_string", query=q, default_operator="and")\
            .execute()
        #
        # web_query = web_query[offset:offset+limit].execute()

        # search everything that is not a directory. The django_ptr_id captures the cms
        # stuff too. 
        query = Search()\
            .query(Q("match", systemId=system_id) | ~Q("exists", field="django_ptr_id"))\
            .query("query_string", query=q, default_operator="and")\
            .query(~Q('match', type='dir'))
        res = query[offset:offset+limit].execute()

        files_query = Search()\
            .query("match", systemId=system_id)\
            .query("query_string", query=q, default_operator="and")\
            .query("match", type="file")\
            .filter("term", _type="object")\
            .execute()

        exp_query = Search()\
            .query("match", systemId=system_id)\
            .query("query_string", query=q, default_operator="and")\
            .filter("term", _type="experiment")\
            .execute()

        projects_query = Search()\
            .query("match", systemId=system_id)\
            .query("query_string", query=q, default_operator="and")\
            .filter("term", _type="project")\
            .execute()

        results = [r for r in res]
        # results.extend([r for r in web_query])
        # results.sort(key=lambda x: x.meta.score, reverse=True)
        out = {}
        hits = []
        # logger.info(hits)
        for r in results:
            d = r.to_dict()
            d["doc_type"] = r.meta.doc_type
            hits.append(d)
        # for wr in web_query:
        #     d = wr.to_dict()
        #     d["doc_type"] = 'cms'
        #     hits.append(d)
        out['total_hits'] = res.hits.total
        out['hits'] = hits
        out['files_total'] = files_query.hits.total
        out['projects_total'] = projects_query.hits.total
        out['experiments_total'] = exp_query.hits.total
        out['cms_total'] = web_query.hits.total
        # projects_query = Q('filtered',
        #                    filter=Q('bool',
        #                             must=Q({'term': {'systemId': system_id}}),
        #                             must_not=Q({'term': {'path._exact': '/'}})),
        #                    query=Q({'simple_query_string': {
        #                             'query': q,
        #                             'fields': ["description",
        #                                        "endDate",
        #                                        "equipment.component",
        #                                        "equipment.equipmentClass",
        #                                        "equipment.facility",
        #                                        "fundorg"
        #                                        "fundorgprojid",
        #                                        "name",
        #                                        "organization.name",
        #                                        "pis.firstName",
        #                                        "pis.lastName",
        #                                        "title"]}}))
        # logger.debug(projects_query)
        # out = {}
        # res = PublicProjectIndexed.search()\
        #         .filter(projects_query)\
        #         .source(include=['description', 'name', 'title', 'project', 'highlight', 'startDate', 'endDate', '_score'])\
        #         .sort('startDate').execute()
        # logger.debug(res)
        # out["projects"] = [r.to_dict() for r in res[offset:limit]]

        # files_query = Q('filtered',
        #                 query=Q({'simple_query_string': {
        #                          'query': q,
        #                          'fields': ['name']}}),
        #                 filter=Q('bool',
        #                          must=Q({'term': {'systemId': system_id}}),
        #                          must_not=Q({'term': {'path._exact': '/'}})))
        # res = PublicObjectIndexed.search()\
        #         .filter(files_query)\
        #         .sort('_score').execute()
        # out["files"] = [r.to_dict() for r in res[offset:limit]]

        # experiments_query = Q('filtered',
        #                    filter=Q('bool',
        #                             must=Q({'term': {'systemId': system_id}}),
        #                             must_not=Q({'term': {'path._exact': '/'}})),
        #                    query=Q({'simple_query_string': {
        #                             'query': q,
        #                             'fields': ["description",
        #                                        "name",
        #                                        "title"]}}))
        # res = PublicExperimentIndexed.search()\
        #         .filter(experiments_query)\
        #         .source(include=['description', 'name', 'title', 'type', 'startDate', 'endDate'])\
        #         .sort('_score').execute()
        # out["experiments"] = [r.to_dict() for r in res[offset:limit]]
        return JsonResponse(out, safe=False)

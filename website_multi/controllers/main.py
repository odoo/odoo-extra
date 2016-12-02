import re

import werkzeug
import openerp
import datetime
from itertools import islice
from openerp.addons.web import http
from openerp.http import request
from openerp.addons.website.controllers.main import Website, SITEMAP_CACHE_TIME, LOC_PER_SITEMAP


class website_multi(Website):

    @http.route('/', type='http', auth="public", website=True)
    def index(self, **kw):
        cr, uid, context = request.cr, request.uid, request.context
        page = 'homepage'
        main_menu = request.website.menu_id
        first_menu = main_menu.child_id and main_menu.child_id[0]
        if first_menu:
            if not (first_menu.url.startswith(('/page/', '/?', '/#')) or (first_menu.url == '/')):
                return request.redirect(first_menu.url)
            if first_menu.url.startswith('/page/'):
                return request.registry['ir.http'].reroute(first_menu.url)
        return self.page(page)

    @http.route('/website/add/<path:path>', type='http', auth="user", website=True)
    def pagenew(self, path, noredirect=False, add_menu=None):
        cr, uid, context = request.cr, request.uid, request.context

        xml_id = request.registry['website'].new_page(request.cr, request.uid, path, context=request.context)
        if add_menu:
            request.registry['website.menu'].create(cr, uid, {
                'name': path,
                'url': '/page/' + xml_id,
                'parent_id': request.website.menu_id.id,
                'website_id': request.website.id
            }, context=context)

        # Reverse action in order to allow shortcut for /page/<website_xml_id>
        url = "/page/" + re.sub(r"^website\.", '', xml_id)

        if noredirect:
            return werkzeug.wrappers.Response(url, mimetype='text/plain')

        return werkzeug.utils.redirect(url)

    @http.route()
    def sitemap_xml_index(self):
        cr, uid, context = request.cr, openerp.SUPERUSER_ID, request.context
        current_website = request.website
        ira = request.registry['ir.attachment']
        iuv = request.registry['ir.ui.view']
        mimetype ='application/xml;charset=utf-8'
        content = None

        def create_sitemap(url, content):
            ira.create(cr, uid, dict(
                datas=content.encode('base64'),
                mimetype=mimetype,
                type='binary',
                name=url,
                url=url,
            ), context=context)

        dom = [('url', '=' , '/sitemap-%d.xml' % current_website.id), ('type', '=', 'binary')]
        sitemap = ira.search_read(cr, uid, dom, ('datas', 'create_date'), limit=1, context=context)

        if sitemap:
            # Check if stored version is still valid
            server_format = openerp.tools.misc.DEFAULT_SERVER_DATETIME_FORMAT
            create_date = datetime.datetime.strptime(sitemap[0]['create_date'], server_format)
            delta = datetime.datetime.now() - create_date
            if delta < SITEMAP_CACHE_TIME:
                content = sitemap[0]['datas'].decode('base64')

        if not content:
            # Remove all sitemaps in ir.attachments as we're going to regenerated them
            dom = [('type', '=', 'binary'), '|', ('url', '=like' , '/sitemap-%d-%%.xml' % current_website.id),
                   ('url', '=' , '/sitemap-%d.xml' % current_website.id)]
            sitemap_ids = ira.search(cr, uid, dom, context=context)
            if sitemap_ids:
                ira.unlink(cr, uid, sitemap_ids, context=context)

            pages = 0
            first_page = None
            locs = current_website.sudo(user=current_website.user_id.id).enumerate_pages()
            while True:
                values = {
                    'locs': islice(locs, 0, LOC_PER_SITEMAP),
                    'url_root': request.httprequest.url_root[:-1],
                }
                urls = iuv.render(cr, uid, 'website.sitemap_locs', values, context=context)
                if urls.strip():
                    page = iuv.render(cr, uid, 'website.sitemap_xml', dict(content=urls), context=context)
                    if not first_page:
                        first_page = page
                    pages += 1
                    create_sitemap('/sitemap-%d-%d.xml' % (current_website.id, pages), page)
                else:
                    break
            if not pages:
                return request.not_found()
            elif pages == 1:
                content = first_page
            else:
                # Sitemaps must be split in several smaller files with a sitemap index
                content = iuv.render(cr, uid, 'website.sitemap_index_xml', dict(
                    pages=range(1, pages + 1),
                    url_root=request.httprequest.url_root,
                ), context=context)
            create_sitemap('/sitemap-%d.xml' % current_website.id, content)

        return request.make_response(content, [('Content-Type', mimetype)])
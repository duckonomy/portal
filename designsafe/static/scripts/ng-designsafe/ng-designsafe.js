//TODO: djng
import $ from 'jquery';
import angular from 'angular';
import _ from 'underscore';

import './services';
import './directives';
import './filters';
import './models';
import './controllers';

export const ngDesignsafe = angular.module('designsafe', 
                                           ['ng.modernizr', 
                                            'djng.urls', 
                                            'slickCarousel', 
                                            'designsafe.services', 
                                            'designsafe.directives', 
                                            'designsafe.filters',
                                            'designsafe.models',
                                            'designsafe.controllers'
                                           ])
.config(['$httpProvider', function($httpProvider) {
  $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
  $httpProvider.defaults.xsrfCookieName = 'csrftoken';
  $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
}])
.config(['WSBusServiceProvider', '$httpProvider', 'toastrConfig',
  function config(WSBusServiceProvider, $httpProvider, toastrConfig) {
    /*
    * https://github.com/Foxandxss/angular-toastr#toastr-customization
    */
    angular.extend(toastrConfig, {
      positionClass: 'toast-bottom-left',
      timeOut: 20000
    });

    WSBusServiceProvider.setUrl(
      (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
      window.location.hostname +
      (window.location.port ? ':' + window.location.port : '') +
      '/ws/websockets?subscribe-broadcast&subscribe-user'
    );
  }
])
.constant('appCategories', ['Simulation', 'Visualization', 'Data Processing', 'Partner Data Apps', 'Utilities'])
// Current list of icons for apps
.constant('appIcons', ['compress', 'extract', 'matlab', 'paraview', 'hazmapper', 'jupyter', 'adcirc', 'qgis', 'ls-dyna', 'ls-pre/post', 'visit', 'openfoam', 'opensees'])

ngDesignsafe.requires.push('django.context', 
                           'httpi',
                           'ngCookies',
                           'djng.urls',  //TODO: djng
                           'ui.bootstrap',
                           'ds.notifications',
                           'toastr',
                           'ds.wsBus',
                           'logging',
                           'ngMaterial');

ngDesignsafe.run(['WSBusService', 'logger',
  function init(WSBusService, logger) {
    WSBusService.init(WSBusService.url);
  }]);
ngDesignsafe.run(['NotificationService', 'logger',
  function init(NotificationService, logger) {
    NotificationService.init();
  }]);





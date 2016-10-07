(function(window, angular) {
  var app = angular.module('DataDepotApp');
  app.controller('DataDepotNavCtrl', ['$scope', '$rootScope', '$state', 'Django', function($scope, $rootScope, $state, Django) {

    $scope.routerItems = [];

    $scope.myDataFileId = 'designsafe.storage.default/' + Django.user + '/';
    $scope.sharedFileId = 'designsafe.storage.default/$SHARE/';

    $scope.routerItems.push({
      name: 'Public',
      collapsible: true,
      collapse: false,
      children: [
        {
          name: 'Publications',
          collapsible: false,
          state: 'publicData'
        },
        {
          name: 'Community Data',
          collapsible: false,
          state: 'communityData'
        },
        {
          name: 'Training Materials',
          collapsible: false,
          state: 'trainingMaterials'
        }
      ]
    });

    if (Django.context.authenticated) {
      $scope.routerItems.splice(0, 0, {
        name: 'Private',
        collapsible: true,
        collapse: false,
        children: [
          {
            name: 'My Data',
            collapsible: false,
            state: 'myData'
          },
          {
            name: 'My Projects',
            collapsible: false,
            state: 'projects.list'
          },
          {
            name: 'My Publications',
            collapsible: false,
            state: 'myPublications'
          },
          {
            name: 'Shared with Me',
            collapsible: false,
            state: 'sharedData'
          },
          {
            name: 'Box.com',
            collapsible: false,
            state: 'boxData'
          }
        ]
      });

      // $scope.routerItems.push({
      //     name: 'Workspace',
      //     collapsible: true,
      //     collapse: true,
      //     children: [
      //       {
      //         name: 'Application Catalog',
      //         collapsible: false,
      //         state: 'applicationCatalog'
      //       },
      //       {
      //         name: 'Run Application',
      //         collapsible: false,
      //         state: 'runApplication'
      //       },
      //       {
      //         name: 'Job History',
      //         collapsible: false,
      //         state: 'jobHistory'
      //       }
      //     ]
      //   }
      // );
    }

    $scope.itemClicked = function(routerItem) {
      if (routerItem.collapsible) {
        routerItem.collapse = ! routerItem.collapse;
      }
    };
  }]);
})(window, angular);

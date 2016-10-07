(function(window, angular, _) {
  var app = angular.module('DataDepotApp');
  app.controller('MyDataCtrl', ['$scope', '$state', 'Django', 'DataBrowserService', function ($scope, $state, Django, DataBrowserService) {

    $scope.browser = DataBrowserService.state();

    $scope.browser.listing.href = $state.href('myData', {system: $scope.browser.listing.system, filePath: $scope.browser.listing.path});
    _.each($scope.browser.listing.children, function (child) {
      child.href = $state.href('myData', {system: child.system, filePath: child.path});
    });

    $scope.data = {
      user: Django.user
    };

    $scope.resolveBreadcrumbHref = function (trailItem) {
      return $state.href('myData', {systemId: $scope.browser.listing.system, filePath: trailItem.path});
    };

    $scope.onBrowse = function ($event, file) {
      $event.preventDefault();
      $event.stopPropagation();
      if (file.type === 'file') {
        DataBrowserService.preview(file);
      } else {
        $state.go('myData', {systemId: file.system, filePath: file.path});
      }
    };

    $scope.onSelect = function($event, file) {
      $event.stopPropagation();

      if ($event.ctrlKey || $event.metaKey) {
        var selectedIndex = $scope.browser.selected.indexOf(file);
        if (selectedIndex > -1) {
          DataBrowserService.deselect([file]);
        } else {
          DataBrowserService.select([file]);
        }
      } else if ($event.shiftKey && $scope.browser.selected.length > 0) {
        var lastFile = $scope.browser.selected[$scope.browser.selected.length - 1];
        var lastIndex = $scope.browser.listing.children.indexOf(lastFile);
        var fileIndex = $scope.browser.listing.children.indexOf(file);
        var min = Math.min(lastIndex, fileIndex);
        var max = Math.max(lastIndex, fileIndex);
        DataBrowserService.select($scope.browser.listing.children.slice(min, max + 1));
      } else {
        DataBrowserService.select([file], true);
      }
    };

    $scope.onDetail = function($event, file) {
      $event.stopPropagation();
      DataBrowserService.preview(file);
    };

  }]);
})(window, angular, _);

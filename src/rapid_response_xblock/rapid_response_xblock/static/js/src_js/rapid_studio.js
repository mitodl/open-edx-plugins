(function($, _) {
  'use strict';

  function RapidResponseAsideStudioView(runtime, element) {
    // we need studio runtime to get handler capable of saving xblock data in Studio
    var studioRuntime = new window.StudioRuntime.v1();

    var toggleUrl = studioRuntime.handlerUrl(element, 'toggle_block_enabled');
    var $element = $(element);

    var rapidTopLevelSel = '.rapid-response-block';
    var rapidBlockContentSel = '.rapid-response-content';
    var enabledCheckboxSel = '.rapid-enabled-toggle';
    var toggleTemplate = _.template($(element).find("#rapid-response-toggle-tmpl").text());
    var rapidResponseToggleInProgress = false;
    function render(state) {
      // Render template
      var $rapidBlockContent = $element.find(rapidBlockContentSel);
      $rapidBlockContent.html(toggleTemplate(state));

      $rapidBlockContent.find(enabledCheckboxSel).click(function(e) {
        if (!rapidResponseToggleInProgress) {
          rapidResponseToggleInProgress = true;
          e.preventDefault();
          runtime.notify('save', {
              state: 'start',
              element: element,
              message: gettext('Toggling rapid response')
          });

          $.post(toggleUrl).then(
            function(state) {
              render(state);
            }
          ).done(function() {
            try {
              window.parent.postMessage({
                type: 'saveEditedXBlockData',
                message: 'Sends a message when the xblock data is saved',
                payload: {}
              }, document.referrer);
            } catch (e) {
              console.error(e);
            }
          }).always(function() {
            runtime.notify('save', {
              state: 'end',
              element: element
            });
          });
          rapidResponseToggleInProgress = false;
        }
      });
    }

    $(function() { // onLoad
      var block = $element.find(rapidTopLevelSel);
      var isEnabled = block.attr('data-enabled') === 'True';
      render({
        is_enabled: isEnabled
      });
    });
  }

  function initializeRapidResponseAside(runtime, element) {
    return new RapidResponseAsideStudioView(runtime, element);
  }

  window.RapidResponseAsideStudioInit = initializeRapidResponseAside;
}($, _));

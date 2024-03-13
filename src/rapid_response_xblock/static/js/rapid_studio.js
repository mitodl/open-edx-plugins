(function($, _) {
  'use strict';

  function RapidResponseAsideStudioView(runtime, element) {
    var toggleEnabledUrl = runtime.handlerUrl(element, '');
    // Redirect this call to our own API instead of xBlock handler because the handler callbacks are not supported
    // for the studio preview. The calls can have two formats 1) "preview/xblock" when called from studio preview
    // 2) "/xblock" when called from Studio plugin(Tab) settings.
    toggleEnabledUrl = toggleEnabledUrl.replace("preview/xblock", "toggle-rapid-response")
    toggleEnabledUrl = toggleEnabledUrl.replace("/xblock", "/toggle-rapid-response")
    var $element = $(element);

    var rapidTopLevelSel = '.rapid-response-block';
    var rapidBlockContentSel = '.rapid-response-content';
    var enabledCheckboxSel = '.rapid-enabled-toggle';
    var toggleTemplate = _.template($(element).find("#rapid-response-toggle-tmpl").text());

    function render(state) {
      // Render template
      var $rapidBlockContent = $element.find(rapidBlockContentSel);
      $rapidBlockContent.html(toggleTemplate(state));

      $rapidBlockContent.find(enabledCheckboxSel).click(function() {
        $.post(toggleEnabledUrl).then(
          function(state) {
            render(state);
          }
        );
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

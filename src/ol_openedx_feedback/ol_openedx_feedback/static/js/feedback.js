(function ($) {
  function initFeedback(initArgs) {
    var blockId = initArgs.block_id;
    var mfeBaseUrl = initArgs.learning_mfe_base_url;
    var payload = initArgs.drawer_payload || {};

    var $trigger = $("#ol-feedback-trigger-" + blockId);
    if (!$trigger.length) {
      return;
    }
    var $anchor = $trigger.closest(".ol-feedback-anchor");

    $trigger.on("click", function (event) {
      event.stopPropagation();
      window.parent.postMessage(
        { type: "ol-feedback::drawer-open", payload: payload },
        mfeBaseUrl || "*"
      );
    });

    // Placement: left of the AskTIM trigger when present, else right-aligned.
    var $chatBtn = $("#chat-button-" + blockId);
    if ($chatBtn.length) {
      $anchor.closest(".ol-feedback-container").addClass("ol-feedback-container--relocated");
      $anchor.addClass("ol-feedback-anchor--docked");
      $chatBtn.before($anchor);
    }
  }

  function FeedbackAsideView(runtime, element, blockElement, initArgs) {
    initFeedback(initArgs);
  }

  window.FeedbackAsideInit = function (runtime, element, blockElement, initArgs) {
    return new FeedbackAsideView(runtime, element, blockElement, initArgs);
  };
})($);

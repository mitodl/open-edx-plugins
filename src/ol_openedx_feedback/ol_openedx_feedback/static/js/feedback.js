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

    // Namespace by block id and clear any prior binding so a re-init rebinds
    // idempotently instead of stacking duplicate click handlers.
    $trigger
      .off("click.olFeedback-" + blockId)
      .on("click.olFeedback-" + blockId, function (event) {
        event.stopPropagation();
        // Post only to the known MFE origin; never "*" (would leak block context).
        if (!mfeBaseUrl) {
          return;
        }
        window.parent.postMessage(
          { type: "ol-feedback::drawer-open", payload: payload },
          mfeBaseUrl
        );
      });

    // Placement: left of the AskTIM trigger when present, else right-aligned.
    var $chatBtn = $("#chat-button-" + blockId);
    if ($chatBtn.length) {
      $anchor.closest(".ol-feedback-container").addClass("ol-feedback-container--relocated");
      $anchor.addClass("ol-feedback-anchor--docked");
      $chatBtn.before($anchor);

      // AskTIM lifts its button with an out-of-flow offset that varies by block
      // type, so align the megaphone's center to the button's rendered position.
      var alignFrame = null;
      var alignToChatButton = function () {
        $anchor.css("transform", "");
        var btnRect = $chatBtn[0].getBoundingClientRect();
        var anchorRect = $anchor[0].getBoundingClientRect();
        var delta =
          (btnRect.top + btnRect.height / 2) -
          (anchorRect.top + anchorRect.height / 2);
        if (Math.abs(delta) > 0.5) {
          $anchor.css("transform", "translateY(" + delta + "px)");
        }
      };
      var scheduleAlign = function () {
        if (alignFrame) {
          window.cancelAnimationFrame(alignFrame);
        }
        alignFrame = window.requestAnimationFrame(alignToChatButton);
      };
      scheduleAlign();
      // Namespace by block id so re-init rebinds idempotently instead of
      // stacking duplicate handlers; rAF collapses resize bursts to one pass.
      $(window)
        .off("resize.olFeedback-" + blockId)
        .on("resize.olFeedback-" + blockId, scheduleAlign);
    }
  }

  function FeedbackAsideView(runtime, element, blockElement, initArgs) {
    initFeedback(initArgs);
  }

  window.FeedbackAsideInit = function (runtime, element, blockElement, initArgs) {
    return new FeedbackAsideView(runtime, element, blockElement, initArgs);
  };
})($);

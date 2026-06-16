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

      // AskTIM shifts its own button up via relative positioning that differs by
      // block type (problem blocks lift it with `bottom: 70px`; video resets it).
      // That offset is outside layout flow, so the docked megaphone would
      // otherwise sit lower than the AskTIM button. Align the megaphone's
      // vertical center to the chat button's actual rendered position — this
      // works for any offset/block type and is a no-op when they already line up.
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
      window.requestAnimationFrame(alignToChatButton);
      $(window).on("resize", alignToChatButton);
    }
  }

  function FeedbackAsideView(runtime, element, blockElement, initArgs) {
    initFeedback(initArgs);
  }

  window.FeedbackAsideInit = function (runtime, element, blockElement, initArgs) {
    return new FeedbackAsideView(runtime, element, blockElement, initArgs);
  };
})($);

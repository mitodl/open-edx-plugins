(function ($) {
  // The megaphone that last opened the drawer. The drawer renders in the parent
  // MFE (cross-origin), so when it closes it can't focus our button directly;
  // it messages us back and we return focus to this trigger.
  var lastTrigger = null;
  // The drawer-closed listener is global, so bind it once across all blocks.
  var closeListenerBound = false;

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
        // Remember which trigger opened the drawer so focus can return here when
        // the drawer closes.
        lastTrigger = $trigger[0];
        window.parent.postMessage(
          { type: "ol-feedback::drawer-open", payload: payload },
          mfeBaseUrl
        );
      });

    // Bind once (not per block): when the drawer closes it posts back so we can
    // return keyboard focus to the megaphone that opened it (WCAG 2.4.3).
    if (!closeListenerBound && mfeBaseUrl) {
      closeListenerBound = true;
      var mfeOrigin;
      try {
        mfeOrigin = new URL(mfeBaseUrl).origin;
      } catch (e) {
        mfeOrigin = mfeBaseUrl;
      }
      window.addEventListener("message", function (event) {
        if (event.origin !== mfeOrigin) {
          return;
        }
        if (
          event.data &&
          event.data.type === "ol-feedback::drawer-closed" &&
          lastTrigger
        ) {
          lastTrigger.focus();
          lastTrigger = null;
        }
      });
    }

    // Placement: left of the AskTIM trigger when present, else right-aligned.
    var $chatBtn = $("#chat-button-" + blockId);
    if ($chatBtn.length) {
      $anchor.closest(".ol-feedback-container").addClass("ol-feedback-container--relocated");
      $anchor.addClass("ol-feedback-anchor--docked");
      // Problem blocks render a horizontal "saved/submit" notification line that
      // runs behind the button row; flag them so CSS can mask it across the gap.
      if (payload.blockType === "problem") {
        $anchor.addClass("ol-feedback-anchor--line-masked");
      }
      $chatBtn.before($anchor);

      // AskTIM lifts its button with an out-of-flow offset that varies by block
      // type, so align the megaphone's center to the button's rendered position.
      var alignFrame = null;
      var alignToChatButton = function () {
        $anchor.css("transform", "");
        var btnRect = $chatBtn[0].getBoundingClientRect();
        // Match the megaphone's height to the AskTIM button so the two stay
        // equal-height peers even when AskTIM's label wraps to two lines on
        // narrow screens (the CSS height is a standalone default).
        $trigger.css("height", btnRect.height + "px");
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

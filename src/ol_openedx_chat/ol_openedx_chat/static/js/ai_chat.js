(function ($) {
  // The button that last opened the drawer. The drawer lives in the parent MFE
  // (cross-origin), so on close it messages us back to refocus this trigger.
  var lastTrigger = null;
  // The message listener is global; bind it once across all blocks.
  var closeListenerBound = false;

  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {
      var mfeBaseUrl = init_args.learning_mfe_base_url;

      $(`#chat-button-${init_args.block_id}`).on(
        "click",
        {
          payload: init_args.drawer_payload,
        },
        function (event) {
          lastTrigger = this;
          // A keyboard-fired click has detail === 0 (mouse is >= 1); pass it so
          // the drawer rings the heading for keyboard opens only.
          var nativeEvent = event.originalEvent || event;
          var viaKeyboard = nativeEvent.detail === 0;

          window.parent.postMessage(
            {
              type: "smoot-design::tutor-drawer-open",
              payload: event.data.payload,
              viaKeyboard: viaKeyboard,
            },
            mfeBaseUrl, // Ensure correct parent origin
          );
        },
      );

      // Return keyboard focus to the trigger on the drawer's post-backs (WCAG 2.4.3).
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
          if (!event.data || !lastTrigger) {
            return;
          }
          if (event.data.type === "smoot-design::tutor-drawer-closed") {
            // Drawer closed: return focus, then forget the trigger.
            lastTrigger.focus();
            lastTrigger = null;
          } else if (
            event.data.type === "smoot-design::tutor-drawer-focus-trigger"
          ) {
            // "Return to block" skip link: refocus the trigger but keep the
            // drawer open (so keep lastTrigger for the later close).
            lastTrigger.focus();
          }
        });
      }
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);

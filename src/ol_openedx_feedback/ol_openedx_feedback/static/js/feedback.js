(function ($) {
  function getCookie(name) {
    var match = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return match ? match.pop() : "";
  }

  function postFeedback(submitUrl, payload) {
    return fetch(submitUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify(payload)
    });
  }

  /* ===== Variant 1 (existing): numeric rating + comment ===== */
  function initVariant1(initArgs) {
    var blockId = initArgs.block_id;
    var submitUrl = initArgs.submit_url;
    var data = initArgs.feedback || {};

    var $openBtn = $("#feedback-button-" + blockId);
    var $modal = $("#ol-feedback-modal-" + blockId);
    var $ratingOptions = $modal.find(".ol-feedback-rating-option");
    var $comment = $modal.find(".ol-feedback-comment");
    var $submit = $modal.find(".ol-feedback-submit");
    var $form = $modal.find(".ol-feedback-form");
    var $success = $modal.find(".ol-feedback-success");
    var $error = $modal.find(".ol-feedback-error");
    var keyNamespace = "keydown.olfeedback-" + blockId;
    var selectedRating = null;

    function openModal() {
      $modal.removeAttr("hidden");
      $ratingOptions.first().focus();
      $(document).on(keyNamespace, function (event) {
        if (event.key === "Escape" || event.keyCode === 27) {
          closeModal();
        }
      });
    }

    function closeModal() {
      $modal.attr("hidden", "hidden");
      $(document).off(keyNamespace);
      $openBtn.focus();
    }

    function setRating(value) {
      selectedRating = value;
      $ratingOptions.attr("aria-checked", "false").removeClass("is-selected");
      $ratingOptions
        .filter('[data-value="' + value + '"]')
        .attr("aria-checked", "true")
        .addClass("is-selected");
      $submit.prop("disabled", false);
    }

    function submitFeedback() {
      if (selectedRating === null) {
        return;
      }
      $submit.prop("disabled", true);
      $error.attr("hidden", "hidden");

      postFeedback(submitUrl, {
        course_id: data.course_id,
        block_usage_key: data.block_usage_key,
        block_type: data.block_type,
        block_display_name: data.block_display_name,
        rating: selectedRating,
        comment: $comment.val() || ""
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("HTTP " + response.status);
          }
          $form.attr("hidden", "hidden");
          $success.removeAttr("hidden");
        })
        .catch(function () {
          $error.removeAttr("hidden");
          $submit.prop("disabled", false);
        });
    }

    $openBtn.on("click", openModal);
    $modal.find("[data-ol-feedback-close]").on("click", closeModal);
    $modal.on("click", function (event) {
      if (event.target === this) {
        closeModal();
      }
    });
    $ratingOptions.on("click", function () {
      setRating(parseInt($(this).attr("data-value"), 10));
    });
    $submit.on("click", submitFeedback);
  }

  /* ===== Variant 2 (new): star rating, low-score reasons, optional comment ===== */
  function initVariant2(initArgs) {
    var blockId = initArgs.block_id;
    var submitUrl = initArgs.submit_url;
    var data = initArgs.feedback || {};

    var $openBtn = $("#feedback-button2-" + blockId);
    var $modal = $("#ol-feedback-stars-" + blockId);
    var $stars = $modal.find(".olfb2-star");
    var $detail = $modal.find("[data-olfb2-detail]");
    var $actions = $modal.find("[data-olfb2-actions]");
    var $chipsWrap = $modal.find("[data-olfb2-chips]");
    var $chips = $modal.find(".olfb2-chip");
    var $comment = $modal.find("[data-olfb2-comment]");
    var $submit = $modal.find("[data-olfb2-submit]");
    var $hint = $modal.find("[data-olfb2-hint]");
    var $more = $modal.find("[data-olfb2-more]");
    var $error = $modal.find("[data-olfb2-error]");
    var $success = $modal.find("[data-olfb2-success]");
    var keyNamespace = "keydown.olfeedback2-" + blockId;
    var rating = null;
    var tags = {};

    function openModal() {
      $modal.removeAttr("hidden");
      $stars.first().focus();
      $(document).on(keyNamespace, function (event) {
        if (event.key === "Escape" || event.keyCode === 27) {
          closeModal();
        }
      });
    }

    function closeModal() {
      $modal.attr("hidden", "hidden");
      $(document).off(keyNamespace);
      $openBtn.focus();
    }

    function paintStars() {
      $stars.each(function () {
        var v = parseInt($(this).attr("data-v"), 10);
        $(this).toggleClass("on", rating !== null && v <= rating);
        $(this).attr("aria-checked", String(v === rating));
      });
    }

    function applyState() {
      paintStars();
      $error.attr("hidden", "hidden");
      if (rating === null) {
        $detail.attr("hidden", "hidden");
        $actions.attr("hidden", "hidden");
        return;
      }
      $actions.removeAttr("hidden");
      $detail.removeAttr("hidden");
      $submit.prop("disabled", false);
      if (rating <= 3) {
        $hint.text("Sorry to hear that — what went wrong?");
        $more.text("Tell us more:");
        $chipsWrap.show();
        $comment.attr("placeholder", "Tell us what's wrong?");
      } else {
        $hint.text("Glad you liked it!");
        $more.text("Anything else? (optional)");
        $chipsWrap.hide();
        tags = {};
        $chips.removeClass("on").attr("aria-pressed", "false");
        $comment.attr("placeholder", "Anything else? (optional)");
      }
    }

    function submitFeedback() {
      if (rating === null) {
        return;
      }
      $submit.prop("disabled", true);
      $error.attr("hidden", "hidden");

      var selected = Object.keys(tags);
      var commentText = $comment.val() || "";
      // No backend change: fold the chosen reasons into the comment field.
      var packed = (selected.length ? "[" + selected.join(", ") + "] " : "") + commentText;

      postFeedback(submitUrl, {
        course_id: data.course_id,
        block_usage_key: data.block_usage_key,
        block_type: data.block_type,
        block_display_name: data.block_display_name,
        rating: rating,
        comment: packed
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("HTTP " + response.status);
          }
          $detail.attr("hidden", "hidden");
          $actions.attr("hidden", "hidden");
          $modal.find(".olfb2-stars").hide();
          $hint.hide();
          $success.removeAttr("hidden");
        })
        .catch(function () {
          $error.removeAttr("hidden");
          $submit.prop("disabled", false);
        });
    }

    $openBtn.on("click", openModal);
    $modal.find("[data-olfb2-close]").on("click", closeModal);
    $modal.on("click", function (event) {
      if (event.target === this) {
        closeModal();
      }
    });
    $stars.on("click", function () {
      rating = parseInt($(this).attr("data-v"), 10);
      $success.attr("hidden", "hidden");
      applyState();
    });
    $chips.on("click", function () {
      var tag = $(this).attr("data-tag");
      if (tags[tag]) {
        delete tags[tag];
        $(this).removeClass("on").attr("aria-pressed", "false");
      } else {
        tags[tag] = true;
        $(this).addClass("on").attr("aria-pressed", "true");
      }
    });
    $submit.on("click", submitFeedback);
  }

  function FeedbackAsideView(runtime, element, blockElement, initArgs) {
    initVariant1(initArgs);
    initVariant2(initArgs);
  }

  window.FeedbackAsideInit = function (runtime, element, blockElement, initArgs) {
    return new FeedbackAsideView(runtime, element, blockElement, initArgs);
  };
})($);

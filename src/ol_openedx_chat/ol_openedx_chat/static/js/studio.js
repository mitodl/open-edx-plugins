(function($) {
    'use strict';

    function OpenLearningChatView(runtime, element, block_element, init_args) {
        var $element = $(element);
        var AIChatConfigUpdateInProgress = false;
        // we need studio runtime to get handler capable of saving xblock data
        var studioRuntime = new window.StudioRuntime.v1();

        $($element).find('.enabled-check').change(function(e) {
            var dataToPost = {"is_enabled": this.checked};
            if (!AIChatConfigUpdateInProgress) {
                AIChatConfigUpdateInProgress = true;

                e.preventDefault();
                runtime.notify('save', {
                    state: 'start',
                    element: element,
                    message: gettext('Updating Chat Config')
                });

                $.ajax({
                    type: 'POST',
                    url: studioRuntime.handlerUrl(element, 'update_chat_config'),
                    data: JSON.stringify(dataToPost),
                    dataType: 'json',
                    contentType: 'application/json; charset=utf-8'
                }).done(function () {
                    window.parent.postMessage(
                        {
                            type: "COURSE_REFRESH_TRIGGER",
                        }, init_args.authoring_mfe_base_url
                    );
                }).always(function() {
                    runtime.notify('save', {
                        state: 'end',
                        element: element
                    });
                    AIChatConfigUpdateInProgress = false;
                });

            }
        });
    }

    function initializeOLChat(runtime, element, block_element, init_args) {
        return new OpenLearningChatView(runtime, element, block_element, init_args);
    }

    window.OLChatInit = initializeOLChat;
}($));

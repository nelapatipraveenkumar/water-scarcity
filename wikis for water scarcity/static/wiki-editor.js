// Initialize TinyMCE editor with media upload capabilities
function initializeEditor() {
    tinymce.init({
        selector: '#content',
        height: 500,
        plugins: 'image media link code autolink lists table',
        toolbar: 'undo redo | formatselect | bold italic | alignleft aligncenter alignright | bullist numlist | link image media | code',
        content_style: 'body { font-family: Arial, sans-serif; }',
        automatic_uploads: true,
        images_upload_url: '/upload_media',
        file_picker_types: 'image media',
        relative_urls: false,
        file_picker_callback: function(cb, value, meta) {
            const input = document.createElement('input');
            input.setAttribute('type', 'file');
            input.setAttribute('accept', meta.filetype === 'image' ? 'image/*' : 'video/*');

            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file.size > 16 * 1024 * 1024) {
                    alert('File size must not exceed 16MB');
                    return;
                }

                const formData = new FormData();
                formData.append('file', file);

                fetch('/upload_media', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(result => {
                    if (result.location) {
                        cb(result.location, { title: file.name });
                    } else {
                        alert('Upload failed');
                    }
                })
                .catch(() => {
                    alert('Upload failed');
                });
            });

            input.click();
        },
        setup: function(editor) {
            editor.on('change', function() {
                editor.save();
            });
        }
    });
}

// Initialize editor when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});
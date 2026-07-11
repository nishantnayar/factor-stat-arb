// Initialize Mermaid diagrams when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({ 
            startOnLoad: true,
            theme: 'default'
        });
    }
});


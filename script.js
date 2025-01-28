
// Declare variables for the scene, camera, renderer, and the 3D engine model
let scene, camera, renderer, engineModel;

// Initialize the 3D scene
function init() {
    // Create a scene
    scene = new THREE.Scene();
    
    // Set up a camera (Field of view, Aspect ratio, Near, Far planes)
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    
    // Create a WebGL renderer
    renderer = new THREE.WebGLRenderer();
    renderer.setSize(window.innerWidth, window.innerHeight); // Set the renderer size to full window
    document.getElementById('model-container').appendChild(renderer.domElement); // Append the renderer canvas to the HTML element

    // Add lighting to the scene (Ambient light for soft white lighting)
    const light = new THREE.AmbientLight(0x404040); // Soft white light
    scene.add(light);
    
    // Load the 3D model (GLTF format) using the GLTFLoader
    const loader = new THREE.GLTFLoader();
    loader.load('models/engine_model.glb', function(gltf) {
        engineModel = gltf.scene; // Load the model into the engineModel variable
        scene.add(engineModel); // Add the model to the scene
        engineModel.scale.set(2, 2, 2); // Scale the model
        engineModel.position.set(0, -1, 0); // Position the model in the scene
        animate(); // Start the animation loop
    });

    // Set the camera position so we can see the model
    camera.position.z = 5;

    // Event listener for window resizing
    window.addEventListener('resize', onWindowResize, false);
}

// Handle window resize events to adjust camera and renderer size
function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight; // Update the aspect ratio
    camera.updateProjectionMatrix(); // Update the camera's projection matrix
    renderer.setSize(window.innerWidth, window.innerHeight); // Resize the renderer
}

// Animation loop to update and render the scene
function animate() {
    requestAnimationFrame(animate); // Request the next frame to keep animation running

    // If the model is loaded, rotate it continuously
    if (engineModel) {
        engineModel.rotation.x += 0.01; // Rotate around X-axis
        engineModel.rotation.y += 0.01; // Rotate around Y-axis
    }

    // Render the scene from the perspective of the camera
    renderer.render(scene, camera);
}

// Function to update the engine description based on the selected engine
function loadEngineDescription(engineName) {
    // Define engine descriptions
    const engineInfo = {
        "Car Engine": "A car engine uses a four-stroke process: intake, compression, power, and exhaust.",
        "Aircraft Engine": "An aircraft engine typically runs on jet propulsion, using combustion to propel the aircraft.",
        "Diesel Engine": "A diesel engine uses compression to ignite the fuel and generate power efficiently."
    };

    // Display the description of the selected engine
    document.getElementById('engine-info').innerText = engineInfo[engineName] || "Select an engine to view details."; 
}

// Function to load a specific engine model based on user selection
function loadModel(engineType) {
    // Clear the previous model if any
    if (engineModel) {
        scene.remove(engineModel);
    }

    // Load the appropriate model based on the selected engine type
    const loader = new THREE.GLTFLoader();
    let modelPath = ''; // Default to an empty string

    // Define model paths based on engine type
    switch(engineType) {
        case 'car':
            modelPath = 'models/car_engine.glb';
            break;
        case 'aircraft':
            modelPath = 'models/aircraft_engine.glb';
            break;
        case 'diesel':
            modelPath = 'models/diesel_engine.glb';
            break;
        default:
            return;
    }

    // Load the selected engine model
    loader.load(modelPath, function(gltf) {
        engineModel = gltf.scene; // Store the model in engineModel
        scene.add(engineModel); // Add the model to the scene
        engineModel.scale.set(2, 2, 2); // Set model scale
        engineModel.position.set(0, -1, 0); // Set model position
        loadEngineDescription(engineType); // Load description for the selected engine
    });
}

// Initialize the scene when the page is loaded
window.onload = init;

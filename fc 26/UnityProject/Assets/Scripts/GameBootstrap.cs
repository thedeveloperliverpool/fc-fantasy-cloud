using System.Collections.Generic;
using UnityEngine;

public class GameBootstrap : MonoBehaviour
{
    void Start()
    {
        CreateEnvironment();
        CreateMatch();
    }

    void CreateEnvironment()
    {
        if (Camera.main == null)
        {
            var camObj = new GameObject("Main Camera");
            var cam = camObj.AddComponent<Camera>();
            camObj.tag = "MainCamera";
            cam.transform.position = new Vector3(-55f, 24f, 0f);
            cam.transform.rotation = Quaternion.Euler(25f, 90f, 0f);
        }

        if (FindObjectOfType<Light>() == null)
        {
            var lightObj = new GameObject("Directional Light");
            var light = lightObj.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            light.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
        }

        var pitch = GameObject.CreatePrimitive(PrimitiveType.Plane);
        pitch.name = "Pitch";
        pitch.transform.position = Vector3.zero;
        pitch.transform.localScale = new Vector3(GameConfig.FieldWidth / 10f, 1f, GameConfig.FieldLength / 10f);
        var renderer = pitch.GetComponent<Renderer>();
        renderer.material.color = new Color(0.1f, 0.45f, 0.2f);

        DrawPitchLines();
        CreateGoals();
    }

    void DrawPitchLines()
    {
        float halfL = GameConfig.FieldLength * 0.5f;
        float halfW = GameConfig.FieldWidth * 0.5f;
        float lineY = 0.02f;
        float thickness = 0.15f;

        CreateLine(new Vector3(-halfW, lineY, -halfL), new Vector3(halfW, lineY, -halfL), thickness);
        CreateLine(new Vector3(halfW, lineY, -halfL), new Vector3(halfW, lineY, halfL), thickness);
        CreateLine(new Vector3(halfW, lineY, halfL), new Vector3(-halfW, lineY, halfL), thickness);
        CreateLine(new Vector3(-halfW, lineY, halfL), new Vector3(-halfW, lineY, -halfL), thickness);

        CreateLine(new Vector3(-halfW, lineY, 0f), new Vector3(halfW, lineY, 0f), thickness);
        CreateCircle(Vector3.zero + Vector3.up * lineY, 9.15f, thickness);

        float boxDepth = 18f;
        float boxWidth = 40f;
        CreateRect(new Vector3(0f, lineY, halfL - boxDepth * 0.5f), boxWidth, boxDepth, thickness);
        CreateRect(new Vector3(0f, lineY, -halfL + boxDepth * 0.5f), boxWidth, boxDepth, thickness);
    }

    void CreateGoals()
    {
        float halfL = GameConfig.FieldLength * 0.5f;
        float halfW = GameConfig.GoalWidth * 0.5f;
        float postHeight = 2.4f;
        float postThickness = 0.2f;

        CreateGoalFrame(new Vector3(0f, 0f, halfL + 0.5f), halfW, postHeight, postThickness);
        CreateGoalFrame(new Vector3(0f, 0f, -halfL - 0.5f), halfW, postHeight, postThickness);
    }

    void CreateGoalFrame(Vector3 center, float halfWidth, float height, float thickness)
    {
        CreatePost(new Vector3(center.x - halfWidth, height * 0.5f, center.z), thickness, height);
        CreatePost(new Vector3(center.x + halfWidth, height * 0.5f, center.z), thickness, height);
        CreateBar(new Vector3(center.x, height, center.z), halfWidth * 2f, thickness);
    }

    void CreatePost(Vector3 pos, float thickness, float height)
    {
        var post = GameObject.CreatePrimitive(PrimitiveType.Cube);
        post.name = "GoalPost";
        post.transform.position = pos;
        post.transform.localScale = new Vector3(thickness, height, thickness);
        post.GetComponent<Renderer>().material.color = Color.white;
    }

    void CreateBar(Vector3 pos, float width, float thickness)
    {
        var bar = GameObject.CreatePrimitive(PrimitiveType.Cube);
        bar.name = "Crossbar";
        bar.transform.position = pos;
        bar.transform.localScale = new Vector3(width, thickness, thickness);
        bar.GetComponent<Renderer>().material.color = Color.white;
    }

    void CreateLine(Vector3 a, Vector3 b, float thickness)
    {
        var line = GameObject.CreatePrimitive(PrimitiveType.Cube);
        line.name = "Line";
        Vector3 mid = (a + b) * 0.5f;
        Vector3 dir = (b - a);
        float length = dir.magnitude;
        dir.y = 0f;
        line.transform.position = mid;
        line.transform.rotation = Quaternion.LookRotation(dir.normalized, Vector3.up);
        line.transform.localScale = new Vector3(thickness, 0.02f, length);
        line.GetComponent<Renderer>().material.color = Color.white;
    }

    void CreateRect(Vector3 center, float width, float depth, float thickness)
    {
        float halfW = width * 0.5f;
        float halfD = depth * 0.5f;
        Vector3 a = new Vector3(center.x - halfW, center.y, center.z - halfD);
        Vector3 b = new Vector3(center.x + halfW, center.y, center.z - halfD);
        Vector3 c = new Vector3(center.x + halfW, center.y, center.z + halfD);
        Vector3 d = new Vector3(center.x - halfW, center.y, center.z + halfD);
        CreateLine(a, b, thickness);
        CreateLine(b, c, thickness);
        CreateLine(c, d, thickness);
        CreateLine(d, a, thickness);
    }

    void CreateCircle(Vector3 center, float radius, float thickness)
    {
        const int segments = 48;
        Vector3 prev = center + new Vector3(radius, 0f, 0f);
        for (int i = 1; i <= segments; i++)
        {
            float angle = (i / (float)segments) * Mathf.PI * 2f;
            Vector3 next = center + new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius);
            CreateLine(prev, next, thickness);
            prev = next;
        }
    }

    void CreateMatch()
    {
        var uiObj = new GameObject("UIManager");
        var ui = uiObj.AddComponent<UIManager>();
        ui.BuildUI();

        var managerObj = new GameObject("MatchManager");
        var manager = managerObj.AddComponent<MatchManager>();
        manager.ui = ui;
        manager.matchActive = false;

        var ballObj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        ballObj.name = "Ball";
        ballObj.transform.position = new Vector3(0f, 0.2f, 0f);
        ballObj.transform.localScale = Vector3.one * 0.5f;
        var ballRb = ballObj.AddComponent<Rigidbody>();
        ballRb.mass = 0.45f;
        ballRb.linearDamping = 0.3f;
        ballRb.angularDamping = 0.05f;
        var ball = ballObj.AddComponent<BallController>();
        manager.ball = ball;

        var homePositions = Formation433(true);
        var awayPositions = Formation433(false);
        manager.home = SpawnTeam("Home", TeamSide.Home, homePositions, new Color(0.15f, 0.35f, 0.85f));
        manager.away = SpawnTeam("Away", TeamSide.Away, awayPositions, new Color(0.85f, 0.2f, 0.2f));

        var careerObj = new GameObject("CareerManager");
        var career = careerObj.AddComponent<CareerManager>();
        career.ui = ui;
        career.match = manager;
    }

    List<PlayerController> SpawnTeam(string name, TeamSide side, List<Vector3> positions, Color color)
    {
        var list = new List<PlayerController>();
        for (int i = 0; i < positions.Count; i++)
        {
            var pObj = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            pObj.name = name + "_" + (i + 1);
            pObj.transform.position = positions[i];
            var renderer = pObj.GetComponent<Renderer>();
            renderer.material.color = color;

            var rb = pObj.AddComponent<Rigidbody>();
            rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;

            var pc = pObj.AddComponent<PlayerController>();
            pc.team = side;
            pc.number = i + 1;
            pc.homePosition = positions[i];
            if (i == 0)
            {
                pc.isGoalkeeper = true;
                renderer.material.color = new Color(0.9f, 0.75f, 0.2f);
            }
            list.Add(pc);
        }
        return list;
    }

    List<Vector3> Formation433(bool home)
    {
        float dir = home ? -1f : 1f;
        float zGoal = GameConfig.FieldLength * 0.5f * dir;
        float zDef = 22f * dir;
        float zMid = 5f * dir;
        float zAtt = -15f * dir;

        return new List<Vector3>
        {
            new Vector3(0f, 1f, zGoal),
            new Vector3(-16f, 1f, zDef),
            new Vector3(-5f, 1f, zDef + 2f),
            new Vector3(5f, 1f, zDef + 2f),
            new Vector3(16f, 1f, zDef),
            new Vector3(-10f, 1f, zMid),
            new Vector3(0f, 1f, zMid + 3f),
            new Vector3(10f, 1f, zMid),
            new Vector3(-12f, 1f, zAtt),
            new Vector3(0f, 1f, zAtt - 2f),
            new Vector3(12f, 1f, zAtt)
        };
    }
}

using UnityEngine;

public class BallController : MonoBehaviour
{
    public PlayerController owner;
    private Rigidbody rb;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
    }

    void FixedUpdate()
    {
        if (owner != null)
        {
            rb.isKinematic = true;
            Vector3 offset = owner.transform.forward * 0.9f + Vector3.up * 0.2f;
            rb.position = owner.transform.position + offset;
        }
        else
        {
            rb.isKinematic = false;
        }
    }

    public void Kick(Vector3 direction, float speed)
    {
        owner = null;
        rb.isKinematic = false;
        rb.linearVelocity = direction.normalized * speed;
    }
}
